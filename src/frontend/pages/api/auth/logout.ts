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
    const response = await fetch('http://user:8080/logout', {  
      method: 'POST',  
      headers: {  
        'Cookie': req.headers.cookie || '',  
      },  
    });  
  
    const data: LogoutResponse = await response.json();  
      
    if (!response.ok) {  
      return res.status(response.status).json(data);  
    }  
      
    // 转发 cookie 清除  
    if (response.headers.get('set-cookie')) {  
      res.setHeader('Set-Cookie', response.headers.get('set-cookie') as string);  
    }  
      
    return res.status(200).json(data);  
  } catch (error) {  
    return res.status(500).json({   
      message: '内部服务器错误',   
      error: error instanceof Error ? error.message : '未知错误'   
    });  
  }  
}