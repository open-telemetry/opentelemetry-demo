import type { NextApiRequest, NextApiResponse } from 'next';

type LoginResponse = {
  message: string;
  sessionid?: string;
  role?: number;
  error?: string;
}

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse<LoginResponse>
) {
  if (req.method !== 'POST') {
    return res.status(405).json({ error: '方法不允许', message: '只允许 POST 请求' });
  }

  try {
    const response = await fetch('http://localhost:10001/login', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(req.body),
    });

    const data: LoginResponse = await response.json();

    if (!response.ok) {
      return res.status(response.status).json(data);
    }

    return res.status(200).json(data);
  } catch (error) {
    return res.status(500).json({
      message: '内部服务器错误',
      error: error instanceof Error ? error.message : '未知错误'
    });
  }
}