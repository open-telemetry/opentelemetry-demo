// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import { createContext, useContext, useEffect, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import ApiGateway from '../gateways/Api.gateway';
import { ProductReview } from '../protos/demo';

interface IContext {
    // null = not loaded yet; [] = loaded with no reviews; array = loaded with reviews.
    productReviews: ProductReview[] | null;
    loading: boolean;
    error: Error | null;
}

export const Context = createContext<IContext>({
    productReviews: null,
    loading: false,
    error: null,
});

interface IProps {
    children: React.ReactNode;
    productId: string;
}

//export const useProductReview = () => useContext(Context);
export const useProductReview = () => {
    const value = useContext(Context);
    return value;
};

const ProductReviewProvider = ({ children, productId }: IProps) => {
    const {
        data,
        isLoading,
        isFetching,
        isError,
        error,
        isSuccess,
    } = useQuery<ProductReview[]>({
        queryKey: ['productReviews', productId],
        queryFn: () => ApiGateway.getProductReviews(productId),
        refetchOnWindowFocus: false,
    });

    // Use a sentinel: null while loading, [] if loaded but empty, array when loaded with data.
    const productReviews: ProductReview[] | null =
        isSuccess ? (data?.productReviews ?? []) : null;

    const loading = isLoading || isFetching;

    // Narrow react-query's `unknown` error to `Error | null`.
    const currentError: Error | null = isError
        ? error instanceof Error
            ? error
            : new Error('Unknown error')
        : null;

    useEffect(() => {
        console.log('ProductReviewProvider productReviews changed:', productReviews);
    }, [productReviews]);

    const value = useMemo(
        () => ({
            productReviews,
            loading,
            error: currentError,
        }),
        [productReviews, loading, currentError]
    );

    return <Context.Provider value={value}>{children}</Context.Provider>;
};

export default ProductReviewProvider;
