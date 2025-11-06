import { check, sleep } from 'k6';
import http from 'k6/http';

// This is the URL we're going to test, in this case the application server.
const url = "http://mythical-server:4000";

// An index of endpoints to use, essentially the paths accepted by the server.
const beasts = [
    'unicorn',
    'manticore',
    'illithid',
    'owlbear',
    'beholder',
];

// The default function is the one that will be run by k6 when it starts.
export default function () {
    // Pick a random beast from the list, then create a random, numeric name.
    const beast = beasts[Math.floor(Math.random() * beasts.length)];
    const randomName = Math.random().toString(36).substring(2, 15) + Math.random().toString(36).substring(2, 15);

    // First check a POST to the application server, we'll use the result of the POST to ensure all is well.
    const resPost = http.post(`${url}/${beast}`, JSON.stringify({ name: randomName }),
        { headers: { 'Content-Type': 'application/json' } });
    // We want to ensure that 201s are returned on a POST, and that the latency is sub-300ms.
    check(resPost, {
        'POST status was 201': (r) => r.status == 201,
        'POST transaction time below 300ms': (r) => r.timings.duration < 300,
    });
    sleep(1);

    // Now we'll ensure we can retrieve the named beast with a GET.
    const resGet = http.get(`${url}/${beast}`);
    // Ensure that the GET returns a 200, and that the latency is sub-300ms.
    check(resGet, {
        'GET status was 200': (r) => r.status == 200,
        'GET transaction time below 300ms': (r) => r.timings.duration < 300,
    });
    sleep(1);

    // Finally we'll remove this entry (to leave the service in good condition) by removing the random name.
    const resDelete = http.del(`${url}/${beast}`, JSON.stringify({ name: randomName }),
        { headers: { 'Content-Type': 'application/json' } });
    // We want to ensure that the application returned a 204 (deletion), and that it was also sub-300ms latency.
    check(resDelete, {
        'DELETE status was 204': (r) => r.status == 204,
        'DELETE transaction time was below 300ms': (r) => r.timings.duration < 300,
    });
    sleep(1);
}
