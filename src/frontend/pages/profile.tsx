import { FC } from 'react';
import withAuth from '../components/withAuth';

const Profile: FC = () => {
  return (
    <div>
      <h1>用户资料</h1>
      <p>这是一个受保护的页面，只有已认证的用户才能访问。</p>
    </div>
  );
};

export default withAuth(Profile);