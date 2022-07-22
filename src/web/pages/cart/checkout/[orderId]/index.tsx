import { NextPage } from 'next';
import Link from 'next/link';
import { useRouter } from 'next/router';
import Button from '../../../../components/Button';
import Footer from '../../../../components/Footer';
import Layout from '../../../../components/Layout';
import Recommendations from '../../../../components/Recommendations';
import { OrderResult } from '../../../../protos/demo';
import AdProvider from '../../../../providers/Ad.provider';
import * as S from '../../../../styles/Checkout.styled';

const Checkout: NextPage = () => {
  const { query } = useRouter();
  const { orderId, shippingTrackingId, items } = JSON.parse((query.order || '{}') as string) as OrderResult;

  return (
    <AdProvider productIds={items.map(({ item }) => item?.productId || '')}>
      <Layout>
        <S.Checkout>
          <S.Container>
            <S.Title>Your order is complete!</S.Title>
            <S.Subtitle>We've sent you a confirmation email.</S.Subtitle>

            <S.DataRow>
              <span>Confirmation #</span>
              <span>{orderId}</span>
            </S.DataRow>
            <S.DataRow>
              <span>Tracking #</span>
              <span>{shippingTrackingId}</span>
            </S.DataRow>
            <S.DataRow>
              <span>Total Paid</span>
              <span>€25.63</span>
            </S.DataRow>
            <S.ButtonContainer>
              <Link href="/">
                <Button type="submit">Continue Shopping</Button>
              </Link>
            </S.ButtonContainer>
          </S.Container>
          <Recommendations />
        </S.Checkout>
        <Footer />
      </Layout>
    </AdProvider>
  );
};

export default Checkout;
