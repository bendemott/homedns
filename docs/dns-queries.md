# DNS Queries
Once your server is running how do you validate it resonds to queries.

## Using NSLOOKUP
Let's assume for a moment your DNS server is hosted at `localhost:53`

We can query our server for an A record:
```shell
nslookup "example.com" localhost
```

## Using Dig
