import type { NextApiRequest, NextApiResponse } from 'next';

const idTranslation: Record<string, string> = {
  OLJCESPC7Z: 'NationalParkFoundationExplorascope.jpg',
  '66VCHSJNUP': 'StarsenseExplorer.jpg',
  '1YMWWN1N4O': 'EclipsmartTravelRefractorTelescope.jpg',
  L9ECAV7KIM: 'LensCleaningKit.jpg',
  '2ZYFJ3GM2N': 'RoofBinoculars.jpg',
  '0PUK6V6EV0': 'SolarSystemColorImager.jpg',
  LS4PSXUNUM: 'RedFlashlight.jpg',
  '9SIQT8TOJO': 'OpticalTubeAssembly.jpg',
  '6E92ZMYYFZ': 'SolarFilter.jpg',
  HQTGWGPNH4: 'TheCometBook.jpg',
};

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
    } else {
      url = `${process.env.LAMBDA_URL}/images?productId=${encodeURIComponent(id)}`;
    }

    console.log(`Fetching image from [${url}]`);
    const r = await fetch(url, { method: 'GET' });

    if (!r.ok) {
      return res.status(r.status).send(await r.text());
    }

    res.setHeader('Content-Type', r.headers.get('Content-Type') ?? 'image/png');
    res.setHeader('Cache-Control', 'public, max-age=300');

    res.status(200).send(Buffer.from(await r.arrayBuffer()));
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : typeof err === 'string' ? err : JSON.stringify(err);
    res.status(500).send(`Proxy error: ${message}`);
  }
}
