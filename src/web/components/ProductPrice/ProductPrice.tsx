import { useCallback, useEffect, useState } from 'react';
import { Money } from '../../protos/demo';
import { useCurrency } from '../../providers/Currency.provider';

interface IProps {
  price: Money;
}

const ProductPrice = ({ price }: IProps) => {
  const [{ units, currencyCode }, setParsedPrice] = useState<Money>(price);
  const { convert, selectedCurrency } = useCurrency();

  const convertPrice = useCallback(async () => {
    const result = await convert(price);

    setParsedPrice(result);
  }, [convert, price]);

  useEffect(() => {
    convertPrice();
  }, [selectedCurrency, price]);

  return (
    <span>
      {currencyCode}
      {units}
    </span>
  );
};

export default ProductPrice;
