"""Basic connection example.
"""

import redis

r = redis.Redis(
    host='level-alpine-exquisite-72906.db.redis.io',
    port=13458,
    decode_responses=True,
    username="default",
    password="TyKZVmMuqv4Iuzz0UspGGR22UHcrsvBI",
)

success = r.set('foo', 'bar')
# True

result = r.get('foo')
print(result)
# >>> bar

