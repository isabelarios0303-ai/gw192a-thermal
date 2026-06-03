// EXPERIMENTAL WebUSB path for the GW192A.
//
// IMPORTANT: WebUSB is unsupported on iOS/Safari and Firefox, and on Android/desktop the OS UVC
// driver usually claims the camera interface, so this path frequently fails. It is provided as a
// best-effort fallback only. The reliable paths are the native Android bridge and the desktop
// gateway. See docs/01-gw192a-research.md and docs/03-platform-strategies.md.

export function isWebUsbSupported(): boolean {
  return typeof navigator !== 'undefined' && 'usb' in navigator;
}

export interface WebUsbResult {
  ok: boolean;
  reason?: string;
  device?: USBDevice;
}

/**
 * Attempt to claim the GW192A via WebUSB. Returns a structured result instead of throwing so the
 * UI can gracefully recommend an alternative capture method.
 */
export async function tryClaimGw192a(): Promise<WebUsbResult> {
  if (!isWebUsbSupported()) {
    return { ok: false, reason: 'WebUSB no está disponible en este navegador (p. ej. iOS/Safari).' };
  }
  try {
    // Filters left broad; production should pin the real idVendor/idProduct of the unit.
    const device = await (navigator as any).usb.requestDevice({ filters: [] });
    await device.open();
    if (device.configuration === null) await device.selectConfiguration(1);

    const iface = device.configuration?.interfaces?.[0];
    if (!iface) return { ok: false, reason: 'No se encontró una interfaz USB utilizable.' };

    try {
      await device.claimInterface(iface.interfaceNumber);
    } catch (e) {
      return {
        ok: false,
        reason:
          'El sistema operativo ya tiene la interfaz UVC (kernel/driver). Usa el gateway de escritorio o la app puente Android.',
      };
    }
    return { ok: true, device };
  } catch (e: any) {
    return { ok: false, reason: e?.message || 'Acceso WebUSB cancelado o no permitido.' };
  }
}

/**
 * Reading UVC isochronous video over WebUSB requires re-implementing the UVC streaming protocol
 * in JS (negotiate format/frame via control transfers, then read iso packets). This is intricate
 * and out of scope for the reference UI; we stop after claiming and direct the user to a reliable
 * capture method. Stub kept to document the contract.
 */
export async function readFrameViaWebUsb(_device: USBDevice): Promise<Uint16Array | null> {
  return null;
}
