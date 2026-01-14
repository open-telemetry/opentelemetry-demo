// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import { NextPage } from 'next';
import Head from 'next/head';
import Link from 'next/link';
import { useRouter } from 'next/router';
import { useEffect } from 'react';
import Ad from '../../../../components/Ad';
import Button from '../../../../components/Button';
import CheckoutItem from '../../../../components/CheckoutItem';
import Layout from '../../../../components/Layout';
import Recommendations from '../../../../components/Recommendations';
import AdProvider from '../../../../providers/Ad.provider';
import * as S from '../../../../styles/Checkout.styled';
import { IProductCheckout } from '../../../../types/Cart';

const Checkout: NextPage = () => {
  const { query } = useRouter();
  const { items = [], shippingAddress, orderId } = JSON.parse((query.order || '{}') as string) as IProductCheckout;

  // Create a custom span for order confirmation
  useEffect(() => {
    if (orderId && typeof window !== 'undefined') {
      // Use the tracer from window if available (initialized in _document.tsx)
      if (typeof (window as any).tracer !== 'undefined') {
        const tracer = (window as any).tracer;
        const span = tracer.startSpan('order.confirmed', {
          attributes: {
            'order.id': orderId,
            'order.items_count': items.length,
            'order.total_items': items.reduce((sum, item) => sum + item.item.quantity, 0),
          },
        });

        console.log('Order confirmation span created:', {
          orderId,
          itemsCount: items.length,
          totalItems: items.reduce((sum, item) => sum + item.item.quantity, 0),
        });

        // End the span immediately as this is just a marker
        span.end();
      }
    }
  }, [orderId, items]);

  return (
    <AdProvider
      productIds={items.map(({ item }) => item?.productId || '')}
      contextKeys={[...new Set(items.flatMap(({ item }) => item.product.categories))]}
    >
      <Head>
        <title>Otel Demo - Order Confirmation</title>
      </Head>
      <Layout>
        <S.Checkout>
          <S.Container>
            <S.Title>Your order is complete!</S.Title>
            <S.Subtitle>We&apos;ve sent you a confirmation email.</S.Subtitle>

            <S.ItemList>
              {items.map(checkoutItem => (
                <CheckoutItem
                  key={checkoutItem.item.productId}
                  checkoutItem={checkoutItem}
                  address={shippingAddress}
                />
              ))}
            </S.ItemList>

            <S.ButtonContainer>
              <Link href="/">
                <Button type="submit">Continue Shopping</Button>
              </Link>
            </S.ButtonContainer>
          </S.Container>
          <Recommendations />
        </S.Checkout>
        <Ad />
      </Layout>
    </AdProvider>
  );
};

export default Checkout;
