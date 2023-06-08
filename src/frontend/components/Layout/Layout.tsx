// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import Header from '../Header';

interface IProps {
  children: React.ReactNode;
}

const Layout = ({ children }: IProps) => {
  return (
    <>
      <Header />
      <main>{children}</main>
    </>
  );
};

export default Layout;
