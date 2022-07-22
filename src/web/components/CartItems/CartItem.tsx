import Link from 'next/link';
import { Product } from '../../protos/demo';
import ProductPrice from '../ProductPrice';
import * as S from './CartItems.styled';

interface IProps {
  product: Product;
  quantity: number;
}

const CartItem = ({
  product: { id, name, picture, priceUsd = { units: 0, nanos: 0, currencyCode: 'USD' } },
  quantity,
}: IProps) => {
  return (
    <S.CartItem>
      <Link href={`/product/${id}`}>
        <S.CartItemImage alt={name} src={picture} />
      </Link>
      <S.CartItemDetails>
        <div>
          <h5>{name}</h5>
          <p>SKU #{id}</p>
        </div>
        <S.PriceContainer>
          <p>Quantity: {quantity}</p>
          <p>
            <ProductPrice price={priceUsd} />
          </p>
        </S.PriceContainer>
      </S.CartItemDetails>
    </S.CartItem>
  );
};

export default CartItem;
