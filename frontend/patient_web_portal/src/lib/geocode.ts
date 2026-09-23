// Address search and reverse lookup, via OpenStreetMap's Nominatim.
//
// Google's Places Autocomplete would need a billing-enabled key, which this
// project does not have — the same reason the maps themselves moved to
// OpenStreetMap. Nominatim needs no key, no account and no card.
//
// Its usage policy caps automated use at roughly one request per second and
// asks that clients identify themselves. Browsers send a Referer
// automatically and forbid setting User-Agent, so the debounce in the
// caller is what keeps this within the policy — do not remove it.

export interface PlaceSuggestion {
  /** Full human-readable address, e.g. "Kovaipudur, Coimbatore, Tamil Nadu". */
  label: string;
  lat: number;
  lng: number;
}

const NOMINATIM = 'https://nominatim.openstreetmap.org';

/** Biased to India: every hospital on this platform is Indian, and an
 *  unbiased search returns a Coimbatore in the wrong country first. */
const COUNTRY = 'in';

async function getJson(url: string, signal?: AbortSignal): Promise<unknown> {
  const res = await fetch(url, {
    signal,
    headers: { Accept: 'application/json' },
  });
  if (!res.ok) throw new Error(`Nominatim ${res.status}`);
  return res.json();
}

/** Address suggestions for a partly-typed address. Empty array on any
 *  failure: a search box that cannot reach the internet should quietly
 *  offer nothing, not block the person from typing the address by hand. */
export async function searchAddress(
  query: string,
  signal?: AbortSignal,
): Promise<PlaceSuggestion[]> {
  const q = query.trim();
  if (q.length < 3) return [];
  try {
    const url =
      `${NOMINATIM}/search?format=jsonv2&addressdetails=1&limit=6` +
      `&countrycodes=${COUNTRY}&q=${encodeURIComponent(q)}`;
    const data = (await getJson(url, signal)) as Array<{
      display_name?: string;
      lat?: string;
      lon?: string;
    }>;
    return (Array.isArray(data) ? data : [])
      .filter((d) => d.display_name && d.lat && d.lon)
      .map((d) => ({
        label: d.display_name as string,
        lat: Number(d.lat),
        lng: Number(d.lon),
      }));
  } catch {
    return [];
  }
}

/** The address at a point, for when someone drops the pin instead of
 *  typing. Returns null rather than throwing — a pin with no address is
 *  still a perfectly good pin, and the coordinates are what routing uses. */
export async function reverseGeocode(
  lat: number,
  lng: number,
  signal?: AbortSignal,
): Promise<string | null> {
  try {
    const url = `${NOMINATIM}/reverse?format=jsonv2&lat=${lat}&lon=${lng}`;
    const data = (await getJson(url, signal)) as { display_name?: string };
    return data?.display_name ?? null;
  } catch {
    return null;
  }
}

/** Why the browser refused to give us a position, in words a person can act
 *  on. The bare "could not access location" this replaces gave no clue
 *  whether it was a denied prompt, a device with GPS off, or a timeout. */
export function geolocationErrorMessage(err: GeolocationPositionError): string {
  switch (err.code) {
    case err.PERMISSION_DENIED:
      return 'Location permission was blocked. Allow location for this site in your browser settings, or drop the pin on the map instead.';
    case err.POSITION_UNAVAILABLE:
      return 'Your device could not determine a position. Check that location is switched on, or drop the pin on the map instead.';
    case err.TIMEOUT:
      return 'Finding your location took too long. Try again, or drop the pin on the map instead.';
    default:
      return 'Could not read your location. Drop the pin on the map instead.';
  }
}
