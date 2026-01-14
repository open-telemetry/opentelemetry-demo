// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import { NextPage } from 'next';
import Head from 'next/head';
import Layout from '../components/Layout';
import ProductList from '../components/ProductList';
import * as S from '../styles/Home.styled';
import { useQuery } from '@tanstack/react-query';
import ApiGateway from '../gateways/Api.gateway';
import Banner from '../components/Banner';
import { CypressFields } from '../utils/enums/CypressFields';
import { useCurrency } from '../providers/Currency.provider';

// Demo error functions for testing RUM source maps
const simulateDatabaseError = () => {
  throw new Error('Demo Error: Failed to fetch user preferences from cache');
};

const processUserData = (userData: any) => {
  // This will trigger the error for demo purposes
  if (userData === null) {
    simulateDatabaseError();
  }
  return userData;
};

const triggerDemoError = () => {
  try {
    // Simulate a realistic error scenario
    const userData = null; // Simulate missing data
    processUserData(userData);
  } catch (error) {
    // Re-throw to ensure it's caught by RUM
    console.error('Demo error triggered for RUM testing:', error);
    throw error;
  }
};

const Home: NextPage = () => {
  const { selectedCurrency } = useCurrency();
  const { data: productList = [] } = useQuery({
    queryKey: ['products', selectedCurrency],
    queryFn: () => ApiGateway.listProducts(selectedCurrency),
  });

  // Handle keyboard shortcut for demo error (Ctrl/Cmd + Shift + E)
  const handleKeyPress = (e: React.KeyboardEvent) => {
    if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key === 'E') {
      e.preventDefault();
      triggerDemoError();
    }
  };

  return (
    <Layout>
      <Head>
        <title>Otel Demo - Home</title>
      </Head>
      <S.Home data-cy={CypressFields.HomePage} onKeyDown={handleKeyPress} tabIndex={0}>
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
        {/* Hidden demo error button - click or use Ctrl/Cmd+Shift+E */}
        <button
          onClick={triggerDemoError}
          style={{
            position: 'fixed',
            bottom: '10px',
            right: '10px',
            padding: '8px 12px',
            background: 'rgba(255, 0, 0, 0.1)',
            border: '1px solid rgba(255, 0, 0, 0.3)',
            borderRadius: '4px',
            cursor: 'pointer',
            fontSize: '11px',
            color: '#666',
            opacity: 0.3,
            transition: 'opacity 0.2s',
          }}
          onMouseEnter={(e) => (e.currentTarget.style.opacity = '1')}
          onMouseLeave={(e) => (e.currentTarget.style.opacity = '0.3')}
          title="Trigger demo error for RUM testing (Ctrl/Cmd+Shift+E)"
        >
          🐛 Demo Error
        </button>
      </S.Home>
    </Layout>
  );
};

export default Home;
