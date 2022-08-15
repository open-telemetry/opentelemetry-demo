import { useCallback, useEffect, useMemo, useState } from 'react';
import getSymbolFromCurrency from 'currency-symbol-map';
import { Money } from '../../protos/demo';
import { useCurrency } from '../../providers/Currency.provider';
import { CypressFields } from '../../utils/Cypress';

interface IProps {
  price: Money;
}

const ProductPrice = ({ price }: IProps) => {
  const [{ units, currencyCode, nanos }, setParsedPrice] = useState<Money>(price);
  const { convert, selectedCurrency } = useCurrency();

  const convertPrice = useCallback(async () => {
    const result = await convert(price);

    setParsedPrice(result);
  }, [convert, price]);

  const currencySymbol = useMemo(
    () => getSymbolFromCurrency(currencyCode) || selectedCurrency,
    [currencyCode, selectedCurrency]
  );

  useEffect(() => {
    convertPrice();
  }, [selectedCurrency, price]);

  return (
    <span data-cy={CypressFields.ProductPrice}>
      {currencySymbol} {units}.{nanos.toString().slice(0, 2)}
    </span>
  );
};

export default ProductPrice;
