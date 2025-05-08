import { useEffect, ComponentType } from 'react';
import { useRouter } from 'next/router';
import { checkAuth } from '../utils/auth';

const withAuth = <P extends object>(WrappedComponent: ComponentType<P>): ComponentType<P> => {
  const AuthComponent = (props: P) => {
    const router = useRouter();

    useEffect(() => {
      if (!checkAuth()) {
        router.push('/login');
      }
    }, [router]);

    return <WrappedComponent {...props} />;
  };

  return AuthComponent;
};

export default withAuth;