// src/frontend/pages/login.tsx
import { useState, FormEvent } from 'react';
import { useRouter } from 'next/router';
import styles from '../styles/login.module.css';

interface LoginResponse {
  message: string;
  sessionid: string;
  role: number;
}

const Login = () => {
  const [username, setUsername] = useState<string>('');
  const [password, setPassword] = useState<string>('');
  const [error, setError] = useState<string>('');
  const router = useRouter();

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    try {
      const response = await fetch('/api/auth/login', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ username, password }),
        credentials: 'include', // 包含 cookie
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || '登录失败');
      }
      const data: LoginResponse = await response.json();
      // 存储会话 ID 和角色信息
      localStorage.setItem('sessionId', data.sessionid);
      localStorage.setItem('userRole', String(data.role));

      // 重定向到首页
      router.push('/');
    } catch (error) {
      setError(error instanceof Error ? error.message : '未知错误');
    }
  };

  return (
    <div className={styles.container}>
      <h2 className={styles.title}>登录</h2>
      {error && <p className={styles.error}>{error}</p>}
      <form onSubmit={handleSubmit}>
        <div className={styles.formGroup}>
          <label className={styles.label}>用户名:</label>
          <input
            type="text"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            required
            className={styles.input}
          />
        </div>
        <div className={styles.formGroup}>
          <label className={styles.label}>密码:</label>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            className={styles.input}
          />
        </div>
        <button type="submit" className={styles.button}>登录</button>
      </form>
    </div>
  );
};

export default Login;