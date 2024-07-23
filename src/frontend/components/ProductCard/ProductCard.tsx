// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import { CypressFields } from '../../utils/Cypress';
import { Product } from '../../protos/demo';
import ProductPrice from '../ProductPrice';
import * as S from './ProductCard.styled';
import { useState, useEffect } from 'react';
import { useNumberFlagValue } from '@openfeature/react-sdk';

interface IProps {
  product: Product;
}

async function getImageWithHeaders(url: RequestInfo, headers: Record<string, string>) {
  const res = await fetch(url, { headers });
  return await res.blob();
}

const ProductCard = ({
  product: {
    id,
    picture,
    name,
    priceUsd = {
      currencyCode: 'USD',
      units: 0,
      nanos: 0,
    },
  },
}: IProps) => {
  const imageSlowLoad = useNumberFlagValue('imageSlowLoad', 0);
  const [imageSrc, setImageSrc] = useState<string>('');

  useEffect(() => {
    const requestInfo = new Request('/images/products/' + picture);
    const headers = { 'x-envoy-fault-delay-request': imageSlowLoad.toString(), 'Cache-Control': 'no-cache' };
    getImageWithHeaders(requestInfo, headers).then(blob => {
      setImageSrc(URL.createObjectURL(blob));
    });
  }, [imageSlowLoad, picture]);

  return (
    <S.Link href={`/product/${id}`}>
      <S.ProductCard data-cy={CypressFields.ProductCard}>
        <S.Image $src={imageSrc} />
        <div>
          <S.ProductName>{name}</S.ProductName>
          <S.ProductPrice>
            <ProductPrice price={priceUsd} />
          </S.ProductPrice>
        </div>
      </S.ProductCard>
    </S.Link>
  );
};

export default ProductCard;
