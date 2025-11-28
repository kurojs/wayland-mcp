# 🚀 Instalación de Wayland MCP - Control Total de PC

## ✅ Estado: CASI LISTO - Requiere permisos sudo

El servidor Wayland MCP está instalado pero necesita algunos paquetes del sistema que requieren permisos de administrador.

## 📦 Instalación Manual Requerida

Ejecuta estos comandos en tu terminal:

```bash
# 1. Instalar evemu-tools (requerido para control de mouse/teclado)
sudo pacman -S evemu

# 2. Ejecutar el script de configuración
cd /home/kuro/Documents/wayland-mcp
sudo bash setup.sh
```

## 🔧 ¿Qué hace el setup.sh?

El script de setup configura los permisos necesarios para que el MCP pueda controlar tu mouse y teclado:

1. **Instala evemu-tools** (si no está instalado)
2. **Configura permisos setuid** para evemu-event
3. **Agrega reglas sudoers** para no pedir contraseña
4. **Añade tu usuario al grupo input**
5. **Crea reglas udev** para acceso persistente a dispositivos

## ⚠️ Seguridad

**IMPORTANTE**: Este MCP tendrá control TOTAL sobre tu mouse y teclado. Solo úsalo en:
- Sistemas de confianza
- Con modelos/servidores confiables
- Cuando realmente necesites automatización

## 🎯 Capacidades una vez instalado

### 📸 Screenshots
- Captura de pantalla completa
- Análisis de imágenes con VLM
- Comparación de imágenes

### 🖱️ Control de Mouse
- Mover el cursor
- Clicks (izquierdo, derecho, medio)
- Arrastrar y soltar
- Scroll vertical/horizontal

### ⌨️ Control de Teclado
- Escribir texto
- Presionar teclas específicas
- Combinaciones de teclas (Ctrl+C, etc.)
- Secuencias complejas de acciones

## 📝 Configuración Actual

Ya está configurado en `/home/kuro/Documents/v1.2.1_Open-LLM-VTuber-v1.2.1-en/mcp_servers.json`:

```json
"wayland-control": {
  "command": "/home/kuro/Documents/wayland-mcp/venv/bin/python",
  "args": ["-m", "wayland_mcp"],
  "env": {
    "XDG_RUNTIME_DIR": "/run/user/1000",
    "WAYLAND_MCP_PORT": "4999",
    "DISPLAY": ":0",
    "WAYLAND_DISPLAY": "wayland-1",
    "XDG_SESSION_TYPE": "wayland"
  }
}
```

## 🚀 Después de la instalación

Una vez que ejecutes los comandos sudo arriba, el MCP estará listo y tu VTuber (o yo en Claude Desktop) podrá:

1. **Ver tu pantalla** - Tomar screenshots y analizar qué hay en la pantalla
2. **Controlar el mouse** - Mover, hacer click, arrastrar
3. **Controlar el teclado** - Escribir, presionar teclas
4. **Automatizar tareas** - Combinar acciones para workflows complejos

## 📋 Verificación

Después de ejecutar el setup, verifica que funciona:

```bash
cd /home/kuro/Documents/wayland-mcp
./venv/bin/python -m wayland_mcp --help
```

Si no hay errores, ¡está listo! 🎉

## 🔗 Integración

Este MCP se integrará automáticamente cuando:
- **Open-LLM-VTuber** se ejecute
- **Claude Desktop** se conecte (si lo tienes configurado)
- Cualquier cliente MCP compatible se conecte

---

**Nota**: Una vez instalado, tendré acceso completo a tu pantalla, mouse y teclado. ¡Úsalo responsablemente! 😊
