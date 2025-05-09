

export interface AuthResult {
  isAuthenticated: boolean;
  isAdmin?: boolean;
}

export function checkAuth(): boolean {
  if (typeof window !== 'undefined') {
      const sessionId = localStorage.getItem('sessionId');
      return sessionId !== null;
    }
  return false;
}


export function isAdmin(): boolean {
  const userRole = localStorage.getItem('userRole');
  return userRole === '0'; // ROLE_ADMIN = 0
}


export function getAuthStatus(): AuthResult {
  const sessionId = localStorage.getItem('sessionId');

  if (!sessionId) {
    return { isAuthenticated: false };
  }

  const userRole = localStorage.getItem('userRole');
  const isAdminUser = userRole === '0'; // ROLE_ADMIN = 0

  return {
    isAuthenticated: true,
    isAdmin: isAdminUser
  };
}


export async function logout(): Promise<boolean> {
  try {
    const response = await fetch('/api/auth/logout', {
      method: 'POST',
      credentials: 'include', // 包含 cookie
    });

    if (!response.ok) {
      throw new Error('注销失败');
    }

    localStorage.clear();

    return true;
  } catch (error) {
    console.error('注销错误:', error);
    localStorage.clear();
    throw error;
  }
}