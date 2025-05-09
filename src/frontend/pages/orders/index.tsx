import { useState, useEffect } from 'react';
import Link from 'next/link';

const OrdersPage = () => {
  const [orders, setOrders] = useState([]);

  useEffect(() => {
    fetchOrders();
  }, []);

  const fetchOrders = async () => {

    try {
      const response = await fetch('/api/orders');

      if (!response.ok) {
        setOrders([]);
      }

      const contentType = response.headers.get("content-type");
      if (!contentType || !contentType.includes("application/json")) {
        setOrders([]);
      }

      const data = await response.json();
      setOrders(data);
    } catch (error) {
      console.error('Failed to fetch orders:', error);
      // 设置一个空数组，避免页面崩溃
      setOrders([]);
    }
  };

  return (
    <div>
      <h1>我的订单</h1>
      {orders.length === 0 ? (
        <p>暂无订单数据，请稍后再试或联系管理员。</p>
      ) : (
        <ul>
          {orders.map((order) => (
            <li key={order.id}>
              <Link href={`/orders/${order.id}`}>
                <a>{`订单 #${order.id}`}</a>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
};

export default OrdersPage;