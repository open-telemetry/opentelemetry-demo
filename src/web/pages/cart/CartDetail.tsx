import Link from 'next/link';
import { useRouter } from 'next/router';
import { useCallback } from 'react';
import Button from '../../components/Button';
import CartItems from '../../components/CartItems';
import CheckoutForm from '../../components/CheckoutForm';
import { IFormData } from '../../components/CheckoutForm/CheckoutForm';
import { useCart } from '../../providers/Cart.provider';
import { useCurrency } from '../../providers/Currency.provider';
import * as S from '../../styles/Cart.styled';

const CartDetail = () => {
  const {
    cart: { items },
    emptyCart,
    placeOrder,
  } = useCart();
  const { selectedCurrency } = useCurrency();
  const { push } = useRouter();

  const onPlaceOrder = useCallback(
    async ({
      email,
      state,
      streetAddress,
      country,
      city,
      zipCode,
      creditCardCvv,
      creditCardExpirationMonth,
      creditCardExpirationYear,
      creditCardNumber,
    }: IFormData) => {
      const order = await placeOrder({
        userId: '123',
        email,
        address: {
          streetAddress,
          state,
          country,
          city,
          zipCode,
        },
        userCurrency: selectedCurrency,
        creditCard: {
          creditCardCvv,
          creditCardExpirationMonth,
          creditCardExpirationYear,
          creditCardNumber,
        },
      });

      push({
        pathname: `/cart/checkout/${order.orderId}`,
        query: { order: JSON.stringify(order) },
      });
    },
    []
  );

  return (
    <S.Container>
      <div>
        <S.Header>
          <S.CarTitle>Cart ({items.length})</S.CarTitle>
          <div>
            <Button
              onClick={async () => {
                await emptyCart();
                push('/');
              }}
              $type="secondary"
              style={{ marginRight: '10px' }}
            >
              Empty Cart
            </Button>
            <Link href="/">
              <Button $type="primary">Continue Shopping</Button>
            </Link>
          </div>
        </S.Header>
        <CartItems productList={items} />
      </div>
      <div>
        <CheckoutForm onSubmit={onPlaceOrder} />
      </div>
    </S.Container>
  );
};

export default CartDetail;
