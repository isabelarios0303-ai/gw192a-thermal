# ThermoBaby Android Bridge (replica de THG Start — Método 3)

App **nativa de Android** que lee la cámara térmica **GW192A** por **USB-OTG** y:

1. **modo local:** muestra la imagen térmica + temperatura en el teléfono (como THG Start), y
2. **modo puente:** envía los frames al servidor ThermoBaby por WebSocket, para que el dashboard
   web (y otros visores) muestren los datos en tiempo real.

> Esto es lo que el navegador **no** puede hacer (iOS bloquea USB; Android no expone UVC a la web
> de forma fiable). Una app nativa **sí** puede pedir el frame crudo y recuperar la temperatura.

## Cómo funciona (igual que THG Start)

La GW192A es una cámara **UVC** que entrega un frame **YUYV de doble altura**: la mitad de arriba
es la imagen visible y la mitad de abajo son **datos radiométricos de 16 bits**. La conversión
(convención InfiRay/Xtherm) es:

```
T(degC) = raw16 / 64 - 273.15
```

La app usa el motor UVC **AndroidUSBCamera (libausbc)**, que envuelve `libuvc` y entrega los
**bytes crudos** del frame (sin que el sistema los convierta a color y borre la temperatura, que
es justo el problema que tuvimos en Windows). Ver `../docs/01-gw192a-research.md`.

```
GW192A --USB-C OTG--> [Android Bridge App] --(local: pantalla)
                                           +--(puente: WebSocket)--> servidor ThermoBaby --> web
```

## Requisitos para compilarla

- **Android Studio** (Giraffe o superior) - https://developer.android.com/studio
- Un **telefono Android** con **USB-OTG** (casi todos los modernos con USB-C).
- La GW192A.

## Como compilar e instalar (resumen)

1. Abre **Android Studio** -> *Open* -> selecciona la carpeta `android-bridge`.
2. Espera a que Gradle descargue dependencias (incluye `libausbc` desde JitPack).
3. Conecta tu telefono por USB con **Depuracion USB** activada.
4. Pulsa **Run**. La app se instala en el telefono.
5. Conecta la GW192A al telefono (USB-C). Acepta el permiso USB que aparece.
6. Veras la imagen termica en vivo. Para enviar al servidor, escribe la URL del servidor
   (ej. `ws://IP-DE-TU-PC:8000`) y pulsa **Conectar**.

> Para el **modo puente**, tu PC (servidor) y el telefono deben estar en la **misma red WiFi**, y
> usas la IP local del PC (ej. `ws://192.168.1.50:8000`).

## Estructura

```
android-bridge/
|- settings.gradle.kts
|- build.gradle.kts
|- gradle.properties
+- app/
   |- build.gradle.kts
   +- src/main/
      |- AndroidManifest.xml
      |- res/xml/device_filter.xml      # filtro USB (clase UVC)
      |- res/layout/activity_main.xml
      |- res/values/strings.xml
      +- java/com/thermobaby/bridge/
         |- MainActivity.kt            # UI, permiso USB, arranque
         |- ThermalDecoder.kt          # frame doble-altura -> Celsius (replica del backend)
         |- FrameProtocol.kt           # empaqueta el frame binario para /ws/ingest
         +- WebSocketUploader.kt       # envia frames al servidor ThermoBaby
```

## Estado y notas honestas

- El **decodificador** (`ThermalDecoder.kt`) y el **protocolo/WebSocket** estan completos y
  reflejan exactamente la logica validada del backend.
- La **integracion con el motor UVC** (callback de frame crudo de `libausbc`) esta cableada con la
  API de AndroidUSBCamera y marcada con comentarios `// AJUSTAR` donde el modelo concreto puede
  requerir afinar geometria (ancho/alto) o el divisor radiometrico - igual que calibramos en PC.
- No se puede compilar dentro de este entorno (sin Android Studio/Gradle); se compila en tu PC con
  Android Studio.

## Creditos / fuentes (reformuladas por cumplimiento de licencias)

- AndroidUSBCamera (jiangdongguo) - motor UVC con acceso a frames crudos.
- UVCCamera (saki4510t) - base UVC para Android.
- Thermal-Camera-Redux (92es) - referencia de decodificacion para la Topdon TC001 (hermana).
- Analisis del formato GW192A: ver `../docs/01-gw192a-research.md`.
