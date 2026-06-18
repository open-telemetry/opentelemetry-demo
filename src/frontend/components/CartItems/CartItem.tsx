// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

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
  const totalNanos = Number(priceUsd.nanos) * quantity;
  const linePrice = {
    units: Number(priceUsd.units) * quantity + Math.floor(totalNanos / 1_000_000_000),
    nanos: totalNanos % 1_000_000_000,
    currencyCode: priceUsd.currencyCode,
  };

  return (
    <S.CartItem>
      <Link href={`/product/${id}`}>
        <S.NameContainer>
          <S.CartItemImage alt={name} src={picture ? "/images/products/" + picture : undefined} />
          <p>{name}</p>
        </S.NameContainer>
      </Link>
      <S.CartItemDetails>
        <p>{quantity}</p>
      </S.CartItemDetails>
      <S.CartItemDetails>
        <S.PriceContainer>
          <p>
            <ProductPrice price={linePrice} />
          </p>
        </S.PriceContainer>
      </S.CartItemDetails>
    </S.CartItem>
  );
};

export default CartItem;
