import { useRouter } from 'next/router';

const OrderDetailPage = () => {
  const router = useRouter();
  const { orderId } = router.query;

  return (
    <div>
      <h1>订单详情: #{orderId}</h1>
    </div>
  );
};

export default OrderDetailPage;