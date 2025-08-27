# Secure Chat Application

Esta aplicación es un sencillo programa de chat punto a punto diseñado para que dos personas puedan comunicarse de forma segura a través de una red local o Internet. Está inspirado en la estética y funcionalidad básica de Discord, pero es completamente independiente y no requiere cuentas de terceros. 

## Características

- **Interfaz de usuario similar a Discord**: utiliza una ventana oscura con una columna lateral para los usuarios conectados y un área principal para el chat.
- **Comunicación cifrada**: todo el texto que viaja por la red se cifra utilizando el algoritmo **Fernet** de la biblioteca [`cryptography`](https://cryptography.io/). Para que dos usuarios puedan comunicarse, ambos deben compartir la misma clave secreta.
- **Modo servidor/cliente**: la aplicación permite actuar como servidor (espera conexiones) o como cliente (se conecta a un servidor). Solo se necesita ejecutar un servidor y un cliente para iniciar la conversación.
- **Modo relay opcional**: ambos usuarios pueden conectarse a un servidor de retransmisión empleando un código de sala, sin compartir direcciones IP.
- **Compatibilidad con Windows**: el programa está escrito en Python 3 y utiliza la biblioteca estándar junto con `cryptography` y `tkinter`, por lo que puede ejecutarse en Windows. Para empaquetarlo como ejecutable de Windows se pueden usar herramientas como `pyinstaller` (no incluida en este proyecto).
- **Chat de voz opcional**: permite enviar audio en tiempo real mediante un botón dedicado.
- **Mensajes coloreados y entrada con sugerencia**: los mensajes del sistema, del usuario local y del remoto se muestran con colores diferentes y el campo de entrada incluye un placeholder que guía al usuario.

## Requisitos

- Python 3.8 o superior.
- Dependencias listadas en `requirements.txt`.
  Puede instalarlas todas con:

  ```bash
  pip install -r requirements.txt
  ```
  Las bibliotecas `sounddevice` y `numpy` son opcionales y solo se utilizan para el chat de voz.

## Uso

1. **Clonar el repositorio:**

   ```bash
   git clone https://github.com/tu-usuario/secure-chat.git
   cd secure-chat
   ```

2. **Instalar dependencias:**

   ```bash
   pip install -r requirements.txt
   ```

3. **Generar una clave secreta (una sola vez):**

   Para cifrar los mensajes, ambos usuarios deben compartir la misma clave. El programa genera una clave automáticamente la primera vez que se ejecuta y la guarda en un archivo `secret.key`. Copie este archivo al segundo ordenador antes de iniciar la comunicación.

4. **Ejecutar el programa:**

   ```bash
   python secure_chat.py
   ```

   La aplicación solicitará un **nombre de usuario** y, a continuación, mostrará un diálogo para elegir el modo **servidor** o **cliente** y solicitará la dirección IP y el puerto correspondientes.

5. **(Opcional) Conectarse a través de un servidor de retransmisión:**

   - Ejecuta `python relay_chat_server.py` en un equipo o VPS accesible por ambos usuarios.
   - Al iniciar la aplicación elige "Servidor" o "Cliente" y responde **Sí** cuando se pregunte por usar el relay.
   - Si actúas como servidor se generará un código de seis dígitos; compártelo con tu contacto.
   - El cliente selecciona también el modo relay e introduce el código para unirse a la sala.
   - El tráfico pasa cifrado por el servidor de retransmisión sin exponer las direcciones IP.
   - La aplicación usa por defecto `localhost:7000` como relay; cambia el host o puerto con las variables `SC_RELAY_HOST` y `SC_RELAY_PORT`.

6. **Conectarse y chatear:**

   - En el ordenador que actuará como servidor seleccione **Servidor**, elija un puerto (por defecto 5000) y pulse **Iniciar**.
   - En el ordenador que actuará como cliente seleccione **Cliente**, introduzca la dirección IP del servidor y el mismo puerto, y pulse **Conectar**.
   - Ambos usuarios pueden escribir mensajes en la parte inferior y estos aparecerán cifrados en la red y descifrados al llegar al destinatario.
   - Con el botón **Voz** es posible iniciar o detener el envío de audio para un chat de voz sencillo. Este botón estará deshabilitado si `sounddevice` o `numpy` no están disponibles.

### Ejecutar en Replit

El repositorio incluye los archivos `.replit` y `replit.nix` para que el proyecto se ejecute en [Replit](https://replit.com/). Al importar el repositorio se instalarán las dependencias de `requirements.txt`.
En Replit no suele haber acceso a dispositivos de audio físicos, por lo que el chat de voz puede no funcionar y el botón **Voz** aparecerá deshabilitado.

## Seguridad

El algoritmo **Fernet** implementa cifrado simétrico autenticado. Esto significa que además de cifrar el contenido asegura que el mensaje no ha sido manipulado en tránsito. Para mantener la privacidad es esencial que la clave secreta no se comparta a través de canales inseguros.

## Empaquetado para Windows

Si desea distribuir la aplicación como un ejecutable para Windows, puede utilizar `pyinstaller`:

```bash
pip install pyinstaller
pyinstaller --onefile --noconsole secure_chat.py
```

Esto generará un archivo `.exe` en la carpeta `dist` que podrá ejecutarse en un sistema Windows sin necesidad de Python instalado.

## Limitaciones

- La aplicación está pensada para dos usuarios. Aunque técnicamente se pueden conectar más clientes al servidor, la interfaz no está preparada para mostrar múltiples canales o conversaciones.
- No incluye validación de certificados ni establecimiento de claves mediante protocolo Diffie‑Hellman; la clave debe compartirse manualmente.

## Licencia

Este proyecto se distribuye bajo la licencia MIT. Consulte el archivo `LICENSE` para más detalles.