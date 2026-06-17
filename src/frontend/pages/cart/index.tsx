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
import { addBreadcrumb } from '../../utils/embrace';
import { maybeCaptureCartPriceMismatchError } from '../../utils/controlledIssues';
import { useCurrency } from '../../providers/Currency.provider';

const Cart: NextPage = () => {
  const {
    cart: { items },
  } = useCart();
  const { selectedCurrency } = useCurrency();

  useEffect(() => {
    addBreadcrumb('cart_viewed');
    maybeCaptureCartPriceMismatchError({
      currency: selectedCurrency,
      itemCount: items.length,
      page: '/cart',
    });
  }, [items.length, selectedCurrency]);

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
