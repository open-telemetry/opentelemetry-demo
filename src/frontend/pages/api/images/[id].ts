import type { NextApiRequest, NextApiResponse } from 'next';

const idTranslation: Record<string, string> = {
  'OLJCESPC7Z': 'NationalParkFoundationExplorascope.jpg',
  '66VCHSJNUP': 'StarsenseExplorer.jpg',
  '1YMWWN1N4O': 'EclipsmartTravelRefractorTelescope.jpg',
  'L9ECAV7KIM': 'LensCleaningKit.jpg',
  '2ZYFJ3GM2N': 'RoofBinoculars.jpg',
  '0PUK6V6EV0': 'SolarSystemColorImager.jpg',
  'LS4PSXUNUM': 'RedFlashlight.jpg',
  '9SIQT8TOJO': 'OpticalTubeAssembly.jpg',
  '6E92ZMYYFZ': 'SolarFilter.jpg',
  'HQTGWGPNH4': 'TheCometBook.jpg',
};

const SCREEN = '860x600';

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  try {
    const { id } = req.query;

    if (typeof id !== 'string') {
      return res.status(400).send('Missing "productId"');
    }

    let url;

    if (process.env.LAMBDA_URL === undefined) {
      const image = idTranslation[id];

      if (image === undefined) {
        return res.status(404).send(`Image for product [${id}] not found`);
      }

      url = `http://image-provider:8081/products/${image}`;

      console.log(`Fetching image from [${url}]`);
      const r = await fetch(url, { method: 'GET' });

      if (!r.ok) {
        return res.status(r.status).send(await r.text());
      }

      res.setHeader('Content-Type', r.headers.get('Content-Type') ?? 'image/png');
      res.setHeader('Cache-Control', 'public, max-age=300');

      res.status(200).send(Buffer.from(await r.arrayBuffer()));
    }

    const presignUrl = new URL(`${process.env.LAMBDA_URL}/images`);
    presignUrl.searchParams.set('productId', id);
    presignUrl.searchParams.set('screen', SCREEN);

    const headers = new Headers();
    headers.set('Cache-Control', 'no-cache');
    headers.set('Accept', 'application/json');

    // Step 1: fetch presigned URL
    const presignResp = await fetch(presignUrl.toString(), { method: 'GET', headers });
    if (!presignResp.ok) {
      const body = await presignResp.text();
      return res.status(presignResp.status).send(`Presign failed: ${body}`);
    }

    const json = (await presignResp.json()) as { url?: string };
    if (!json?.url || typeof json.url !== 'string') {
      return res.status(502).send('Presign endpoint returned an invalid payload');
    }
    
    // Step 2: fetch the image directly from S3 via the presigned URL
    const imgResp = await fetch(json.url, { method: 'GET' });
    if (!imgResp.ok) {
      return res.status(imgResp.status).send(await imgResp.text());
    }
    
    // Respond to the browser
    res.setHeader('Content-Type', imgResp.headers.get('Content-Type') ?? 'image/png');
    // Forward upstream cache header if present; otherwise default to 5 minutes
    res.setHeader('Cache-Control', 'no-cache');

    const buf = Buffer.from(await imgResp.arrayBuffer());
    return res.status(200).send(buf);

  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : typeof err === 'string' ? err : JSON.stringify(err);
    res.status(500).send(`Proxy error: ${message}`);
  }
}
