// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import Header from '../Header';
import Footer from '../Footer';
import AssistantPanel from '../AssistantPanel';

interface IProps {
  children: React.ReactNode;
}

const Layout = ({ children }: IProps) => {
  return (
    <>
      <Header />
      <main>{children}</main>
      <Footer />
      <AssistantPanel />
    </>
  );
};

export default Layout;
