// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import { NextPage } from 'next';
import Head from 'next/head';
import { useEffect } from 'react';
import Layout from '../components/Layout';
import ProductList from '../components/ProductList';
import * as S from '../styles/Home.styled';
import { useQuery } from '@tanstack/react-query';
import ApiGateway from '../gateways/Api.gateway';
import Banner from '../components/Banner';
import { CypressFields } from '../utils/enums/CypressFields';
import { useCurrency } from '../providers/Currency.provider';
import { addBreadcrumb, endEmbraceSpan, startEmbraceSpan } from '../utils/embrace';

const Home: NextPage = () => {
  const { selectedCurrency } = useCurrency();
  const { data: productList = [], isSuccess } = useQuery({
    queryKey: ['products', selectedCurrency],
    queryFn: () => ApiGateway.listProducts(selectedCurrency),
  });

  useEffect(() => {
    addBreadcrumb('home_viewed');
    startEmbraceSpan('browse_products_flow', {
      currency: selectedCurrency,
      page: '/',
    });
  }, [selectedCurrency]);

  useEffect(() => {
    if (!isSuccess || productList.length === 0) return;

    addBreadcrumb('product_list_viewed');
    endEmbraceSpan('browse_products_flow', true);
  }, [isSuccess, productList.length]);

  return (
    <Layout>
      <Head>
        <title>Otel Demo - Home</title>
      </Head>
      <S.Home data-cy={CypressFields.HomePage}>
        <Banner />
        <S.Container>
          <S.Row>
            <S.Content>
              <S.HotProducts>
                <S.HotProductsTitle data-cy={CypressFields.HotProducts} id="hot-products">
                  Hot Products
                </S.HotProductsTitle>
                <ProductList productList={productList} />
              </S.HotProducts>
            </S.Content>
          </S.Row>
        </S.Container>
      </S.Home>
    </Layout>
  );
};

export default Home;
