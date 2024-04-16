// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import Image from 'next/image';
import { useState } from 'react';
import { CypressFields } from '../../utils/Cypress';
import { Address } from '../../protos/demo';
import { IProductCheckoutItem } from '../../types/Cart';
import ProductPrice from '../ProductPrice';
import * as S from './CheckoutItem.styled';

interface IProps {
  checkoutItem: IProductCheckoutItem;
  address: Address;
}

interface ImageLoaderProps {
  src: string;
  width: number;
  quality?: number;
}
/**
 * We connect to imageprovider through the envoy proxy, straight from the browser, for this we need to know the current hostname and port.
 * During building and serverside rendering, these are undefined so we use some conditionals and default values.
 */
let hostname = "";
let port = 80;
let protocol = "http";

if (typeof window !== "undefined" && window.location) {
  hostname = window.location.hostname;
  port = window.location.port ? parseInt(window.location.port, 10) : (window.location.protocol === "https:" ? 443 : 80);
  protocol = window.location.protocol.slice(0, -1); // Remove trailing ':'
}
const imageLoader = ({ src, width, quality }: ImageLoaderProps): string => {
  // We pass down the optimization request to the iamgeprovider service here, without this, nextJs would trz to use internal optimizer which is not working with the external imageprovider.
  return `${protocol}://${hostname}:${port}/${src}?w=${width}&q=${quality || 75}`;
}


const CheckoutItem = ({
  checkoutItem: {
    item: {
      quantity,
      product: { picture, name },
    },
    cost = { currencyCode: 'USD', units: 0, nanos: 0 },
  },
  address: { streetAddress = '', city = '', state = '', zipCode = '', country = '' },
}: IProps) => {
  const [isCollapsed, setIsCollapsed] = useState(false);

  return (
    <S.CheckoutItem data-cy={CypressFields.CheckoutItem}>
      <S.ItemDetails>
        <S.ItemImage src={"/images/products/" + picture} alt={name} loader={imageLoader}/>
        <S.Details>
          <S.ItemName>{name}</S.ItemName>
          <p>Quantity: {quantity}</p>
          <p>
            Total: <ProductPrice price={cost} />
          </p>
        </S.Details>
      </S.ItemDetails>
      <S.ShippingData>
        <S.ItemName>Shipping Data</S.ItemName>
        <p>Street: {streetAddress}</p>
        {!isCollapsed && <S.SeeMore onClick={() => setIsCollapsed(true)}>See More</S.SeeMore>}
        {isCollapsed && (
          <>
            <p>City: {city}</p>
            <p>State: {state}</p>
            <p>Zip Code: {zipCode}</p>
            <p>Country: {country}</p>
          </>
        )}
      </S.ShippingData>
      <S.Status>
        <Image src="/icons/Check.svg" alt="check" height="14" width="16" /> <span>Done</span>
      </S.Status>
    </S.CheckoutItem>
  );
};

export default CheckoutItem;
