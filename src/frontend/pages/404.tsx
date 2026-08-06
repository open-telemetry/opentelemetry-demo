// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import { NextPage } from 'next';
import Head from 'next/head';
import * as S from '../styles/Error.styled';

// Kept free of data-fetching components (Layout/Header) on purpose: Next.js
// may render this page on both the client and server, and it should not
// depend on anything that could itself fail.
const NotFoundPage: NextPage = () => {
  return (
    <>
      <Head>
        <title>Otel Demo - Page Not Found</title>
      </Head>
      <S.Container>
        <S.Code>404</S.Code>
        <S.Message>This page could not be found.</S.Message>
        <S.HomeLink href="/">Go to homepage</S.HomeLink>
      </S.Container>
    </>
  );
};

export default NotFoundPage;
