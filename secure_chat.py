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
import base64
import tkinter as tk
from tkinter import simpledialog, messagebox, scrolledtext

try:
    import numpy as np  # type: ignore
except Exception:  # pragma: no cover - fallback when numpy is missing
    np = None  # type: ignore
try:
    import sounddevice as sd  # type: ignore
except Exception:  # pragma: no cover - fallback when sounddevice is missing
    sd = None  # type: ignore
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

        # Solicitar nombre de usuario
        username = simpledialog.askstring(
            "Usuario",
            "Introduce tu nombre de usuario",
            parent=self.master,
        )
        if not username or not username.strip():
            self.master.destroy()
            return
        self.username = username.strip()
        self.peer_username = "Amigo"

        # Cola para mensajes entrantes
        self.msg_queue = queue.Queue()

        # Socket de red
        self.conn = None  # tipo: socket.socket | None
        self.receiver_thread = None

        # Voz
        self.voice_streaming = False
        self.voice_enabled = sd is not None and np is not None
        self.play_stream = None

        # Interfaz gráfica
        self.create_widgets()

        # Configurar conexión (modal)
        self.setup_connection()

        # Procesar mensajes entrantes periódicamente
        self.master.after(100, self.process_incoming_messages)

        # Cierre ordenado
        self.master.protocol("WM_DELETE_WINDOW", self.on_close)

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
            (
                "Se ha generado un archivo 'secret.key' con la clave de cifrado.\n"
                "Copia este archivo al otro ordenador antes de iniciar la comunicación."
            ),
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
            text="Usuarios",
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

        # Añadir usuario local
        self.add_user_to_list(f"{self.username} (tú)")

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
        # Colores para distintos tipos de mensajes
        self.chat_area.tag_config('self', foreground='#1db954')
        self.chat_area.tag_config('peer', foreground='#00b0f4')
        self.chat_area.tag_config('system', foreground='#ffcc00')
        self.chat_area.tag_config('voice', foreground='#faa61a')

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
        # Placeholder para guiar al usuario
        self.placeholder = "Escribe un mensaje..."
        self.entry.insert(0, self.placeholder)
        self.entry.config(fg="#72767d")
        self.entry.bind("<FocusIn>", self.clear_placeholder)
        self.entry.bind("<FocusOut>", self.add_placeholder)

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

        self.voice_btn = tk.Button(
            self.input_frame,
            text="Voz",
            bg="#7289da",
            fg="#ffffff",
            activebackground="#5865f2",
            activeforeground="#ffffff",
            borderwidth=0,
            font=("Segoe UI", 10, "bold"),
            command=self.toggle_voice_chat
        )
        if not self.voice_enabled:
            self.voice_btn.config(state=tk.DISABLED)
        self.voice_btn.pack(side=tk.RIGHT, padx=5, pady=5)

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
        server_socket.close()
        self.conn = conn
        # Las operaciones de interfaz deben ejecutarse en el hilo principal
        def setup_ui() -> None:
            self.append_message(
                f"[Sistema] Conectado con {addr[0]}:{addr[1]}\n"
            )
        self.master.after(0, setup_ui)
        # Hilo para recibir mensajes
        self.receiver_thread = threading.Thread(target=self.receive_messages, daemon=True)
        self.receiver_thread.start()
        self.send_username()

    def connect_to_server(self, host: str, port: int) -> None:
        """Se conecta a un servidor existente."""
        conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        conn.connect((host, port))
        self.append_message(f"[Sistema] Conectado al servidor {host}:{port}\n")
        self.conn = conn
        # Hilo para recibir mensajes
        self.receiver_thread = threading.Thread(target=self.receive_messages, daemon=True)
        self.receiver_thread.start()
        self.send_username()

    def send_username(self) -> None:
        """Envía nuestro nombre de usuario al compañero."""
        if not self.conn:
            return
        try:
            token = self.cipher.encrypt(f"USER:{self.username}".encode("utf-8"))
            self.conn.sendall(token + b"\n")
        except Exception:
            pass

    def send_message(self) -> None:
        """Envía el mensaje escrito en el cuadro de entrada."""
        if not self.conn:
            return
        text = self.entry.get().strip()
        if not text or text == self.placeholder:
            return
        try:
            token = self.cipher.encrypt(text.encode('utf-8'))  # bytes
            # Añadimos salto de línea para separar mensajes
            self.conn.sendall(token + b'\n')
            self.append_message(f"{self.username}: {text}\n")
            self.entry.delete(0, tk.END)
            self.add_placeholder()
        except Exception as e:
            messagebox.showerror("Error", f"Error al enviar mensaje: {e}")

    def receive_messages(self) -> None:
        """Recibe datos del socket, incluyendo audio y mensajes de texto."""
        buffer = b""
        try:
            while True:
                data = self.conn.recv(4096)
                if not data:
                    self.msg_queue.put("[Sistema] Conexión cerrada\n")
                    break
                buffer += data
                while b'\n' in buffer:
                    token, buffer = buffer.split(b'\n', 1)
                    if not token:
                        continue
                    if token.startswith(b'VOICE:'):
                        b64 = token[6:]
                        if sd is None or np is None:
                            self.msg_queue.put(
                                "[Voz] Audio recibido pero sounddevice o numpy no están disponibles\n"
                            )
                            continue
                        try:
                            audio_bytes = base64.b64decode(b64)
                            audio = np.frombuffer(audio_bytes, dtype='float32').reshape(-1, 1)
                            if self.play_stream is None:
                                self.play_stream = sd.OutputStream(
                                    samplerate=44100, channels=1, dtype='float32'
                                )
                                self.play_stream.start()
                            self.play_stream.write(audio)
                        except Exception:
                            self.msg_queue.put("[Error voz] No se pudo reproducir audio\n")
                        continue
                    try:
                        decrypted = self.cipher.decrypt(token)
                        message = decrypted.decode('utf-8')
                    except Exception:
                        message = "[Error] No se pudo descifrar un mensaje."
                    if message.startswith("USER:"):
                        name = message[5:]
                        self.peer_username = name
                        self.master.after(0, lambda: self.add_user_to_list(name))
                        self.msg_queue.put(f"[Sistema] {name} se ha unido\n")
                        continue
                    if message == "SYS:VOICE:START":
                        self.msg_queue.put(
                            f"[Voz] {self.peer_username} se unió al chat de voz\n"
                        )
                        continue
                    if message == "SYS:VOICE:STOP":
                        self.msg_queue.put(
                            f"[Voz] {self.peer_username} salió del chat de voz\n"
                        )
                        continue
                    self.msg_queue.put(f"{self.peer_username}: {message}\n")
        except Exception as e:
            self.msg_queue.put(f"[Error] {e}\n")
        finally:
            if self.play_stream is not None:
                try:
                    self.play_stream.close()
                except Exception:
                    pass
                self.play_stream = None
            if self.conn:
                try:
                    self.conn.close()
                finally:
                    self.conn = None
            # Eliminar al usuario remoto de la lista cuando la conexión termina
            self.master.after(0, self.remove_peer_from_list)

    def process_incoming_messages(self) -> None:
        """Procesa mensajes de la cola y los muestra en el área de chat."""
        while not self.msg_queue.empty():
            msg = self.msg_queue.get_nowait()
            self.append_message(msg)
        # Programar próxima comprobación
        self.master.after(100, self.process_incoming_messages)

    def append_message(self, msg: str) -> None:
        """Añade un mensaje al área de chat con estilo según el remitente."""
        tag = 'default'
        if msg.startswith(f"{self.username}:"):
            tag = 'self'
        elif msg.startswith(f"{self.peer_username}:"):
            tag = 'peer'
        elif msg.startswith("[Sistema]"):
            tag = 'system'
        elif msg.startswith("[Voz]"):
            tag = 'voice'
        self.chat_area.configure(state=tk.NORMAL)
        self.chat_area.insert(tk.END, msg, tag)
        self.chat_area.configure(state=tk.DISABLED)
        self.chat_area.yview(tk.END)

    def clear_placeholder(self, _event=None) -> None:
        """Elimina el texto del placeholder cuando el usuario enfoca la entrada."""
        if self.entry.get() == self.placeholder:
            self.entry.delete(0, tk.END)
            self.entry.config(fg="#dcddde")

    def add_placeholder(self, _event=None) -> None:
        """Restablece el placeholder si la entrada está vacía."""
        if not self.entry.get():
            self.entry.insert(0, self.placeholder)
            self.entry.config(fg="#72767d")

    def add_user_to_list(self, username: str) -> None:
        """Añade un usuario a la lista lateral."""
        if username not in self.user_list.get(0, tk.END):
            self.user_list.insert(tk.END, username)

    def remove_peer_from_list(self) -> None:
        """Elimina al usuario remoto de la lista lateral, si está presente."""
        for i, name in enumerate(self.user_list.get(0, tk.END)):
            if name == self.peer_username:
                self.user_list.delete(i)
                break
        self.peer_username = "Amigo"

    # --- Voz ---

    def toggle_voice_chat(self) -> None:
        """Inicia o detiene el envío de audio."""
        if not self.voice_enabled:
            messagebox.showwarning(
                "Voz no disponible",
                "sounddevice o numpy no están instalados o no hay dispositivo de audio.",
            )
            return
        if self.voice_streaming:
            self.voice_streaming = False
            self.voice_btn.config(text="Voz")
            if self.conn:
                try:
                    token = self.cipher.encrypt(b"SYS:VOICE:STOP")
                    self.conn.sendall(token + b"\n")
                except Exception:
                    pass
            self.append_message("[Voz] Saliste del chat de voz\n")
            return
        if not self.conn:
            messagebox.showwarning("Sin conexión", "Conéctate antes de usar el chat de voz.")
            return
        self.voice_streaming = True
        self.voice_btn.config(text="Detener voz")
        if self.conn:
            try:
                token = self.cipher.encrypt(b"SYS:VOICE:START")
                self.conn.sendall(token + b"\n")
            except Exception:
                pass
        self.append_message("[Voz] Te uniste al chat de voz\n")
        threading.Thread(target=self.capture_voice, daemon=True).start()

    def capture_voice(self) -> None:
        """Captura audio del micrófono y lo envía al compañero."""
        if sd is None or np is None:
            self.msg_queue.put("[Error voz] sounddevice o numpy no disponibles\n")
            return
        try:
            with sd.InputStream(samplerate=44100, channels=1, dtype='float32') as stream:
                while self.voice_streaming and self.conn:
                    data, _ = stream.read(1024)
                    if not data.size:
                        continue
                    b64 = base64.b64encode(data.tobytes())
                    try:
                        self.conn.sendall(b'VOICE:' + b64 + b'\n')
                    except Exception:
                        break
        except Exception as e:
            self.msg_queue.put(f"[Error voz] {e}\n")
        finally:
            if self.voice_streaming and self.conn:
                try:
                    token = self.cipher.encrypt(b"SYS:VOICE:STOP")
                    self.conn.sendall(token + b"\n")
                except Exception:
                    pass
            self.voice_streaming = False
            self.master.after(0, lambda: self.voice_btn.config(text="Voz"))

    def on_close(self) -> None:
        """Cierra la aplicación limpiando recursos."""
        self.voice_streaming = False
        if self.play_stream is not None:
            try:
                self.play_stream.close()
            except Exception:
                pass
            self.play_stream = None
        if self.conn:
            try:
                self.conn.shutdown(socket.SHUT_RDWR)
            except Exception:
                pass
            self.conn.close()
            self.conn = None
        self.master.destroy()


def main() -> None:
    root = tk.Tk()
    app = SecureChatApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()

