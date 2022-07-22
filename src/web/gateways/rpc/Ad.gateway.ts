import { ChannelCredentials } from '@grpc/grpc-js';
import { AdResponse, AdServiceClient } from '../../protos/demo';

const client = new AdServiceClient('localhost:9555', ChannelCredentials.createInsecure());

const AdGateway = () => ({
  listAds(productIds: string[]) {
    return new Promise<AdResponse>((resolve, reject) =>
      client.getAds({ contextKeys: productIds }, (error, response) => (error ? reject(error) : resolve(response)))
    );
  },
});

export default AdGateway();
