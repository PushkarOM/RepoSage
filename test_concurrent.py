import asyncio
import httpx

async def main():
    async with httpx.AsyncClient(base_url="http://localhost", timeout=10.0) as client:
        # Login
        r = await client.post("/api/login",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            content="username=repro_user&password=hunter2")
        print("login:", r.status_code)
        cookies = dict(r.cookies)
        print("cookies received:", list(cookies.keys()))

        # Send 2 concurrent /api/refresh with same cookies
        # httpx shares the cookie jar across requests in the same client
        # and DOES send the most recently set cookies -- but we just got
        # the cookies from login so they are stable
        cookie_header = "; ".join(f"{k}={v}" for k, v in cookies.items())
        print("\nFiring 2 concurrent /api/refresh:")
        t1 = httpx.AsyncClient(base_url="http://localhost", timeout=10.0)
        results = await asyncio.gather(
            t1.post("/api/refresh", headers={"Cookie": cookie_header}),
            t1.post("/api/refresh", headers={"Cookie": cookie_header}),
        )
        for i, r in enumerate(results):
            print(f"refresh #{i+1}: {r.status_code}")
        await t1.aclose()

asyncio.run(main())