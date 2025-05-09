// src/frontend/pages/api/auth/logout.ts  
import type { NextApiRequest, NextApiResponse } from 'next';  
  
type LogoutResponse = {  
  message: string;  
  error?: string;  
}  
  
export default async function handler(  
  req: NextApiRequest,   
  res: NextApiResponse<LogoutResponse>  
) {  
  if (req.method !== 'POST') {  
    return res.status(405).json({ error: '方法不允许', message: '只允许 POST 请求' });  
  }  
  
  try {  
    const response = await fetch('http://localhost:10001/logout', {
      method: 'POST',
      credentials: 'include',
    });
    const data: LogoutResponse = await response.json();
    if (!response.ok) {  
      return res.status(response.status).json(data);  
    }
    return res.status(200).json(data);  
  } catch (error) {
    console.error(error)
  }  
}