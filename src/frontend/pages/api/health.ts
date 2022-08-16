import type { NextApiRequest, NextApiResponse } from 'next';

type TResponse = string;

export default function handler(_: NextApiRequest, res: NextApiResponse<TResponse>) {
    return res.status(200).send("ok")
}
