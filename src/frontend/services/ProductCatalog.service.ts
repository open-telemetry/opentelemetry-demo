// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import ProductCatalogGateway from '../gateways/rpc/ProductCatalog.gateway';
import CurrencyGateway from '../gateways/rpc/Currency.gateway';
import { Money } from '../protos/demo';
import logger from '../utils/telemetry/logger';

const defaultCurrencyCode = 'USD';

const ProductCatalogService = () => ({
  async getProductPrice(price: Money, currencyCode: string) {
    if (!!currencyCode && currencyCode !== defaultCurrencyCode) {
      try {
        return await CurrencyGateway.convert(price, currencyCode);
      } catch (error) {
        logger.warn({ err: error, currencyCode }, 'Failed to convert product price, falling back to base currency');
        return price;
      }
    }
    return price;
  },
  async listProducts(currencyCode = 'USD') {
    const { products: productList } = await ProductCatalogGateway.listProducts();

    return Promise.all(
      productList.map(async product => {
        const priceUsd = await this.getProductPrice(product.priceUsd!, currencyCode);

        return {
          ...product,
          priceUsd,
        };
      })
    );
  },
  async getProduct(id: string, currencyCode = 'USD') {
    const product = await ProductCatalogGateway.getProduct(id);

    return {
      ...product,
      priceUsd: await this.getProductPrice(product.priceUsd!, currencyCode),
    };
  },
});

export default ProductCatalogService();
