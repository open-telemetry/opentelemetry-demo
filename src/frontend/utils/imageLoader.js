  /*
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
 
  export default function imageLoader({ src, width, quality }) {
    // We pass down the optimization request to the iamgeprovider service here, without this, nextJs would try to use internal optimizer which is not working with the external imageprovider.
    return `${protocol}://${hostname}:${port}/${src}?w=${width}&q=${quality || 75}`
  }
