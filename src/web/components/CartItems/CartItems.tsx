import { useMemo } from 'react';
import { useQuery } from 'react-query';
import ApiGateway from '../../gateways/Api.gateway';
import { Money } from '../../protos/demo';
import { IProductCartItem } from '../../types/Cart';
import ProductPrice from '../ProductPrice';
import CartItem from './CartItem';
import * as S from './CartItems.styled';

interface IProps {
  productList: IProductCartItem[];
}

const CartItems = ({ productList }: IProps) => {
  const { data: shippingConst = { units: 0, currencyCode: 'USD', nanos: 0 } } = useQuery('shipping', () =>
    ApiGateway.getShippingCost(productList)
  );

  const total = useMemo<Money>(
    () => ({
      units:
        productList.reduce((acc, item) => acc + (item.product.priceUsd?.units || 0) * item.quantity, 0) +
        (shippingConst?.units || 0),
      currencyCode: 'USD',
      nanos: 0,
    }),
    [shippingConst, productList]
  );

  return (
    <S.CartItems>
      {productList.map(({ productId, product, quantity }) => (
        <CartItem key={productId} product={product} quantity={quantity} />
      ))}
      <S.DataRow>
        <span>Shipping</span>
        <ProductPrice price={shippingConst} />
      </S.DataRow>
      <S.DataRow>
        <S.TotalText>Total</S.TotalText>
        <S.TotalText>
          <ProductPrice price={total} />
        </S.TotalText>
      </S.DataRow>
    </S.CartItems>
  );
};

export default CartItems;
