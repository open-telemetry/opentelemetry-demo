// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import { createContext, useContext, useEffect, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import ApiGateway from '../gateways/Api.gateway';
import { ProductReview, GetProductReviewSummaryResponse } from '../protos/demo';

interface IContext {
    // null = not loaded yet; [] = loaded with no reviews; array = loaded with reviews.
    productReviews: ProductReview[] | null;
    loading: boolean;
    error: Error | null;
    productReviewSummary: GetProductReviewSummaryResponse | null;
}

export const Context = createContext<IContext>({
    productReviews: null,
    loading: false,
    error: null,
    productReviewSummary: null,
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
    const productReviews: ProductReview[] | null = isSuccess
        ? Array.isArray(data)
            ? data
            : []
        : null;

    const loading = isLoading || isFetching;

    // Narrow react-query's `unknown` error to `Error | null`.
    const currentError: Error | null = isError
        ? error instanceof Error
            ? error
            : new Error('Unknown error')
        : null;

    const { data: productReviewSummary = { averageScore: '', productReviewSummary: '' } } = useQuery({
        queryKey: ['productReviewSummary', productId],
        queryFn: () => ApiGateway.getProductReviewSummary(productId),
    });

    const value = useMemo(
        () => ({
            productReviews,
            loading,
            error: currentError,
            productReviewSummary,
        }),
        [productReviews, loading, currentError, productReviewSummary]
    );

    return <Context.Provider value={value}>{children}</Context.Provider>;
};

export default ProductReviewProvider;
