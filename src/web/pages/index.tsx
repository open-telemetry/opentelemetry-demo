import { NextPage } from 'next';
import Footer from '../components/Footer';
import Layout from '../components/Layout';
import ProductList from '../components/ProductList';
import * as S from '../styles/Home.styled';
import { useQuery } from 'react-query';
import ApiGateway from '../gateways/Api.gateway';

const Home: NextPage = () => {
  const { data: productList = [] } = useQuery('products', ApiGateway.listProducts);

  return (
    <Layout>
      <S.Home>
        <S.MobileHeroBanner />
        <S.Container>
          <S.Row>
            <S.DesktopHeroBanner />
            <S.Content>
              <S.HotProducts>
                <h1>Hot Products</h1>
                <ProductList productList={productList} />
              </S.HotProducts>
              <Footer />
            </S.Content>
          </S.Row>
        </S.Container>
      </S.Home>
    </Layout>
  );
};

export default Home;
