// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import { NextPage } from 'next';
import Head from 'next/head';
import { useEffect } from 'react';
import Layout from '../../components/Layout';
import Recommendations from '../../components/Recommendations';
import * as S from '../../styles/Cart.styled';
import CartDetail from '../../components/Cart/CartDetail';
import EmptyCart from '../../components/Cart/EmptyCart';
import { useCart } from '../../providers/Cart.provider';
import AdProvider from '../../providers/Ad.provider';

const Cart: NextPage = () => {
  const {
    cart: { items },
  } = useCart();

  // Simulate a CartPageError workflow for Splunk RUM demo purposes
  useEffect(() => {
    if (items.length > 0 && typeof window !== 'undefined' && (window as any).tracer) {
      const tracer = (window as any).tracer;
      const span = tracer.startSpan('CartPageError', {
        attributes: {
          'workflow.name': 'CartPageError',
          'error': true,
        },
      });

      console.error("Uncaught TypeError: Cannot read property 'Price' of undefined");
      span.end();
    }
  }, [items.length]);

  return (
    <AdProvider
      productIds={items.map(({ productId }) => productId)}
      contextKeys={[...new Set(items.flatMap(({ product }) => product.categories))]}
    >
      <Head>
        <title>Otel Demo - Cart</title>
      </Head>
      <Layout>
        <S.Cart>
          {(!!items.length && <CartDetail />) || <EmptyCart />}
          <Recommendations />
        </S.Cart>
      </Layout>
    </AdProvider>
  );
};

export default Cart;
