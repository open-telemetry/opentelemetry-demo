// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import { NextPage } from 'next';
import Head from 'next/head';
import Footer from '../../components/Footer';
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
        <Footer />
      </Layout>
    </AdProvider>
  );
};

export default Cart;
