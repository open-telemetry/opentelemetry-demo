import { ChannelCredentials } from '@grpc/grpc-js';
import { AdResponse, AdServiceClient } from '../../protos/demo';

const { AD_SERVICE_ADDR = '' } = process.env;

const client = new AdServiceClient(AD_SERVICE_ADDR, ChannelCredentials.createInsecure());

const AdGateway = () => ({
  listAds(contextKeys: string[]) {
    return new Promise<AdResponse>((resolve, reject) =>
      client.getAds({ contextKeys: contextKeys }, (error, response) => (error ? reject(error) : resolve(response)))
    );
  },
});

export default AdGateway();
