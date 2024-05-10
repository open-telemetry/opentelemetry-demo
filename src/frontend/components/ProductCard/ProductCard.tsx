// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import { CypressFields } from '../../utils/Cypress';
import { Product } from '../../protos/demo';
import ProductPrice from '../ProductPrice';
import * as S from './ProductCard.styled';
import { useState, useEffect } from 'react';
import { RequestInfo } from 'undici-types';
import { useNumberFlagValue, OpenFeature } from '@openfeature/react-sdk';
import { FlagdWebProvider } from '@openfeature/flagd-web-provider';

interface IProps {
  product: Product;
}

async function getImageWithHeaders(url: RequestInfo, headers: Record<string,string>) {
  const res = await fetch(url, { headers });
  return await res.blob();
}

/**
 * We connect to flagd through the envoy proxy, straight from the browser, for this we need to know the current hostname and port.
 * During building and serverside rendering, these are undefined so we use some conditionals and default values.
 */
let hostname = "";
let port = 80;
let tls = false;

if (typeof window !== "undefined" && window.location) {
  hostname = window.location.hostname;
  port = window.location.port ? parseInt(window.location.port, 10) : 80;
  tls = window.location.protocol === "https:";
}


OpenFeature.setProvider(new FlagdWebProvider({
  host: hostname,
  pathPrefix: "flagservice",
  port: port,
  tls: tls,
  maxRetries: 3,
  maxDelay: 10000,
}));


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
  }
}: IProps) => {

  const imageSlowLoad = useNumberFlagValue('imageSlowLoad', 0);
  const headers = {'x-envoy-fault-delay-request': imageSlowLoad.toString(),
                  'Cache-Control': 'no-cache'}
  
  const [imageSrc, setImageSrc] =useState<string>("");

  useEffect(() => {
    getImageWithHeaders("/images/products/" + picture, headers).then((blob) => {
      setImageSrc(URL.createObjectURL(blob));
    });
  }, [picture]);



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
