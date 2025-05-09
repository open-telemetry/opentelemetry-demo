// import { FC } from 'react';
// import { useEffect, useState } from 'react';
// import { useRouter } from 'next/router';
// import Link from 'next/link';
// import { checkAuth, logout } from '../utils/auth';
//
// const Navbar: FC = () => {
//   const router = useRouter();
//   const [isAuthenticated, setIsAuthenticated] = useState(false);
//
//     useEffect(() => {
//       setIsAuthenticated(checkAuth());
//     }, [router.pathname]);
//
//   const handleLogout = async (): Promise<void> => {
//     try {
//       await logout();
//       router.push('/login');
//     } catch (error) {
//       console.error('注销失败:', error);
//     }
//   };
//
//   return (
//     <nav className="navbar">
//       <div className="navbar-brand">
//         <Link href="/" legacyBehavior>
//           <a>OpenTelemetry Demo</a>
//         </Link>
//       </div>
//       <div className="navbar-menu">
//         {isAuthenticated ? (
//           <button onClick={handleLogout} className="logout-button">
//             注销
//           </button>
//         ) : (
//           <Link href="/login" legacyBehavior>
//             <a className="login-link">登录</a>
//           </Link>
//         )}
//       </div>
//       <style jsx>{`
//         .navbar {
//           display: flex;
//           justify-content: space-between;
//           align-items: center;
//           padding: 1rem 2rem;
//           background-color: #f8f9fa;
//           box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
//         }
//         .navbar-brand a {
//           font-size: 1.25rem;
//           font-weight: bold;
//           text-decoration: none;
//           color: #333;
//         }
//         .logout-button {
//           background-color: #dc3545;
//           color: white;
//           border: none;
//           padding: 0.5rem 1rem;
//           border-radius: 4px;
//           cursor: pointer;
//         }
//         .login-link {
//           color: #007bff;
//           text-decoration: none;
//         }
//       `}</style>
//     </nav>
//   );
// };
//
// export default Navbar;