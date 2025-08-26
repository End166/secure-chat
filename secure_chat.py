"""
Aplicación de chat seguro basada en interfaz y funcionalidad de Discord.

Permite a dos personas comunicarse a través de una conexión de red utilizando un cifrado
simétrico (Fernet) para garantizar la confidencialidad de los mensajes. La interfaz de
usuario se construye con Tkinter y trata de emular un aspecto oscuro similar a Discord.

Uso:
    python secure_chat.py

Al iniciar la aplicación se mostrará un cuadro de diálogo para elegir si se actúa
como servidor o cliente y solicitará la dirección IP y el puerto. Para cifrar los
mensajes se utiliza una clave almacenada en el archivo `secret.key`. Si este archivo
no existe se genera automáticamente una nueva clave y se indica al usuario que debe
compartirla con la otra persona.

Limitaciones:
    - Sólo se soporta una conexión cliente-servidor simultánea.
    - La clave de cifrado debe compartirse de forma segura con el corresponsal.
    - No hay verificación de identidad ni intercambio de claves.
"""

import os
import socket
import threading
import queue
import tkinter as tk
from tkinter import simpledialog, messagebox, scrolledtext

from cryptography.fernet import Fernet


class SecureChatApp:
    """Clase principal de la aplicación de chat seguro."""

    def __init__(self, master: tk.Tk):
        self.master = master
        self.master.title("Secure Chat")
        # Configuración del tema oscuro
        self.master.configure(bg="#2f3136")
        self.master.geometry("600x400")

        # Carga o generación de la clave
        self.key = self.load_or_create_key()
        self.cipher = Fernet(self.key)

        # Cola para mensajes entrantes
        self.msg_queue = queue.Queue()

        # Socket de red
        self.conn = None  # tipo: socket.socket | None
        self.receiver_thread = None

        # Interfaz gráfica
        self.create_widgets()

        # Configurar conexión (modal)
        self.setup_connection()

        # Procesar mensajes entrantes periódicamente
        self.master.after(100, self.process_incoming_messages)

    def load_or_create_key(self) -> bytes:
        """Carga una clave de cifrado desde 'secret.key' o genera una nueva si no existe."""
        key_path = os.path.join(os.path.dirname(__file__), 'secret.key')
        if os.path.exists(key_path):
            with open(key_path, 'rb') as f:
                key = f.read().strip()
            return key
        # Generar nueva clave
        key = Fernet.generate_key()
        with open(key_path, 'wb') as f:
            f.write(key)
        messagebox.showinfo(
            "Clave generada",
            "Se ha generado un archivo 'secret.key' con la clave de cifrado.\n"
            "Copia este archivo al otro ordenador antes de iniciar la comunicación."
        )
        return key

    def create_widgets(self) -> None:
        """Crea los elementos de la interfaz gráfica."""
        # Marco principal para chat y barra lateral
        self.main_frame = tk.Frame(self.master, bg="#36393f")
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        # Barra lateral (lista de usuarios)
        self.sidebar = tk.Frame(self.main_frame, bg="#2f3136", width=150)
        self.sidebar.pack(side=tk.LEFT, fill=tk.Y)
        self.sidebar.pack_propagate(False)

        self.user_label = tk.Label(
            self.sidebar,
            text="Conectado",
            bg="#2f3136",
            fg="#ffffff",
            font=("Arial", 12, "bold")
        )
        self.user_label.pack(pady=10)

        self.user_list = tk.Listbox(
            self.sidebar,
            bg="#2f3136",
            fg="#ffffff",
            selectbackground="#7289da",
            highlightthickness=0,
        )
        self.user_list.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Marco del chat
        self.chat_frame = tk.Frame(self.main_frame, bg="#36393f")
        self.chat_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        # Área de mensajes
        self.chat_area = scrolledtext.ScrolledText(
            self.chat_frame,
            bg="#36393f",
            fg="#dcddde",
            insertbackground="#dcddde",
            wrap=tk.WORD,
            state=tk.DISABLED,
            font=("Segoe UI", 10)
        )
        self.chat_area.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Área de entrada
        self.input_frame = tk.Frame(self.chat_frame, bg="#40444b")
        self.input_frame.pack(fill=tk.X, padx=5, pady=5)

        self.entry = tk.Entry(
            self.input_frame,
            bg="#40444b",
            fg="#dcddde",
            insertbackground="#dcddde",
            borderwidth=0,
            font=("Segoe UI", 10)
        )
        self.entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 0), pady=5)
        self.entry.bind("<Return>", lambda event: self.send_message())

        self.send_btn = tk.Button(
            self.input_frame,
            text="Enviar",
            bg="#7289da",
            fg="#ffffff",
            activebackground="#5865f2",
            activeforeground="#ffffff",
            borderwidth=0,
            font=("Segoe UI", 10, "bold"),
            command=self.send_message
        )
        self.send_btn.pack(side=tk.RIGHT, padx=5, pady=5)

    def setup_connection(self) -> None:
        """Muestra un diálogo para seleccionar modo (servidor/cliente) y establece la conexión."""
        mode = simpledialog.askstring(
            "Modo de conexión",
            "Elige modo:\nServidor o Cliente",
            initialvalue="Servidor",
            parent=self.master
        )
        if mode is None:
            # Usuario canceló
            self.master.destroy()
            return
        mode = mode.strip().lower()
        if mode not in {"servidor", "cliente"}:
            messagebox.showerror("Error", "Modo no válido. Debe ser 'Servidor' o 'Cliente'.")
            self.master.destroy()
            return

        if mode == "servidor":
            # Solicitar puerto
            port = simpledialog.askinteger(
                "Puerto",
                "Introduce el puerto para escuchar (por defecto 5000)",
                initialvalue=5000,
                parent=self.master
            )
            if port is None:
                self.master.destroy()
                return
            try:
                self.start_server(port)
            except Exception as e:
                messagebox.showerror("Error", f"Error al iniciar servidor: {e}")
                self.master.destroy()
                return
        else:
            # Cliente: solicitar dirección y puerto
            host = simpledialog.askstring(
                "Dirección IP",
                "Introduce la dirección IP o nombre del servidor",
                parent=self.master
            )
            if host is None:
                self.master.destroy()
                return
            port = simpledialog.askinteger(
                "Puerto",
                "Introduce el puerto del servidor",
                initialvalue=5000,
                parent=self.master
            )
            if port is None:
                self.master.destroy()
                return
            try:
                self.connect_to_server(host.strip(), port)
            except Exception as e:
                messagebox.showerror("Error", f"Error al conectar con el servidor: {e}")
                self.master.destroy()
                return

    # Conexión y comunicación
    def start_server(self, port: int) -> None:
        """Inicia el servidor y espera una conexión."""
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind(("", port))
        server_socket.listen(1)
        self.append_message(f"[Sistema] Servidor escuchando en el puerto {port}\n")
        threading.Thread(
            target=self.accept_connection,
            args=(server_socket,),
            daemon=True
        ).start()

    def accept_connection(self, server_socket: socket.socket) -> None:
        """Espera y acepta una conexión entrante."""
        conn, addr = server_socket.accept()
        self.append_message(f"[Sistema] Conectado con {addr[0]}:{addr[1]}\n")
        self.add_user_to_list(f"Amigo ({addr[0]})")
        self.conn = conn
        # Hilo para recibir mensajes
        self.receiver_thread = threading.Thread(target=self.receive_messages, daemon=True)
        self.receiver_thread.start()

    def connect_to_server(self, host: str, port: int) -> None:
        """Se conecta a un servidor existente."""
        conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        conn.connect((host, port))
        self.append_message(f"[Sistema] Conectado al servidor {host}:{port}\n")
        self.add_user_to_list(f"Servidor ({host})")
        self.conn = conn
        # Hilo para recibir mensajes
        self.receiver_thread = threading.Thread(target=self.receive_messages, daemon=True)
        self.receiver_thread.start()

    def send_message(self) -> None:
        """Envía el mensaje escrito en el cuadro de entrada."""
        if not self.conn:
            return
        text = self.entry.get().strip()
        if not text:
            return
        try:
            token = self.cipher.encrypt(text.encode('utf-8'))  # bytes
            # Añadimos salto de línea para separar mensajes
            self.conn.sendall(token + b'\n')
            self.append_message(f"Tú: {text}\n")
            self.entry.delete(0, tk.END)
        except Exception as e:
            messagebox.showerror("Error", f"Error al enviar mensaje: {e}")

    def receive_messages(self) -> None:
        """Recibe mensajes cifrados del socket, los descifra y los añade a la cola."""
        buffer = b""
        while True:
            try:
                data = self.conn.recv(4096)
                if not data:
                    # conexión cerrada
                    self.msg_queue.put("[Sistema] Conexión cerrada\n")
                    break
                buffer += data
                # Procesar mensajes completos separados por salto de línea
                while b'\n' in buffer:
                    token, buffer = buffer.split(b'\n', 1)
                    if not token:
                        continue
                    try:
                        decrypted = self.cipher.decrypt(token)
                        message = decrypted.decode('utf-8')
                    except Exception:
                        message = "[Error] No se pudo descifrar un mensaje."
                    self.msg_queue.put(f"Amigo: {message}\n")
            except Exception as e:
                self.msg_queue.put(f"[Error] {e}\n")
                break

    def process_incoming_messages(self) -> None:
        """Procesa mensajes de la cola y los muestra en el área de chat."""
        while not self.msg_queue.empty():
            msg = self.msg_queue.get_nowait()
            self.append_message(msg)
        # Programar próxima comprobación
        self.master.after(100, self.process_incoming_messages)

    def append_message(self, msg: str) -> None:
        """Añade un mensaje al área de chat de manera segura (hilo principal)."""
        self.chat_area.configure(state=tk.NORMAL)
        self.chat_area.insert(tk.END, msg)
        self.chat_area.configure(state=tk.DISABLED)
        self.chat_area.yview(tk.END)

    def add_user_to_list(self, username: str) -> None:
        """Añade un usuario a la lista lateral."""
        if username not in self.user_list.get(0, tk.END):
            self.user_list.insert(tk.END, username)


def main() -> None:
    root = tk.Tk()
    app = SecureChatApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()