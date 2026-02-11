> ## Documentation Index
> Fetch the complete documentation index at: https://docs.perplexity.ai/llms.txt
> Use this file to discover all available pages before exploring further.

# Best Practices

> Learn best practices for using the Perplexity SDKs in production, including environment variables, rate limiting, security, and efficient request patterns.

## Overview

This guide covers essential best practices for using the Perplexity SDKs in production environments. Following these practices will help you build robust, secure, and efficient applications.

## Security Best Practices

### Environment Variables

Always store API keys securely using environment variables:

<Steps>
  <Step title="Use environment variables">
    Store API keys in environment variables, never in source code.

    <CodeGroup>
      ```python Python theme={null}
      import os
      from perplexity import Perplexity

      # Good: Use environment variables
      client = Perplexity(
          api_key=os.environ.get("PERPLEXITY_API_KEY")
      )

      # Bad: Never hardcode API keys
      # client = Perplexity(api_key="pplx-abc123...")  # DON'T DO THIS
      ```

      ```typescript Typescript theme={null}
      import Perplexity from '@perplexity-ai/perplexity_ai';

      // Good: Use environment variables
      const client = new Perplexity({
          apiKey: process.env.PERPLEXITY_API_KEY
      });

      // Bad: Never hardcode API keys
      // const client = new Perplexity({
      //     apiKey: "pplx-abc123..."  // DON'T DO THIS
      // });
      ```
    </CodeGroup>

    <Warning>
      Never commit API keys to version control. Use .env files locally and secure environment variable management in production.
    </Warning>
  </Step>

  <Step title="Use .env files for local development">
    Create a `.env` file for local development (add it to .gitignore):

    ```bash  theme={null}
    cat > .env << 'EOF'
    PERPLEXITY_API_KEY=your_api_key_here
    PERPLEXITY_MAX_RETRIES=3
    PERPLEXITY_TIMEOUT=30000
    EOF
    ```

    <CodeGroup>
      ```python Python theme={null}
      from dotenv import load_dotenv
      import os
      from perplexity import Perplexity

      # Load environment variables from .env file
      load_dotenv()

      client = Perplexity(
          api_key=os.getenv("PERPLEXITY_API_KEY"),
          max_retries=int(os.getenv("PERPLEXITY_MAX_RETRIES", "3"))
      )
      ```

      ```typescript Typescript theme={null}
      import dotenv from 'dotenv';
      import Perplexity from '@perplexity-ai/perplexity_ai';

      // Load environment variables from .env file
      dotenv.config();

      const client = new Perplexity({
          apiKey: process.env.PERPLEXITY_API_KEY,
          maxRetries: parseInt(process.env.PERPLEXITY_MAX_RETRIES || '3')
      });
      ```
    </CodeGroup>
  </Step>

  <Step title="Validate environment variables">
    Check for required environment variables at startup.

    <CodeGroup>
      ```python Python theme={null}
      import os
      import sys
      from perplexity import Perplexity

      def create_client():
          api_key = os.getenv("PERPLEXITY_API_KEY")
          if not api_key:
              print("Error: PERPLEXITY_API_KEY environment variable is required")
              sys.exit(1)
          
          return Perplexity(api_key=api_key)

      client = create_client()
      ```

      ```typescript Typescript theme={null}
      import Perplexity from '@perplexity-ai/perplexity_ai';

      function createClient(): Perplexity {
          const apiKey = process.env.PERPLEXITY_API_KEY;
          if (!apiKey) {
              console.error("Error: PERPLEXITY_API_KEY environment variable is required");
              process.exit(1);
          }
          
          return new Perplexity({ apiKey });
      }

      const client = createClient();
      ```
    </CodeGroup>
  </Step>
</Steps>

### API Key Rotation

Implement secure API key rotation:

<CodeGroup>
  ```python Python theme={null}
  import os
  import logging
  from perplexity import Perplexity
  from typing import Optional

  class SecurePerplexityClient:
      def __init__(self, primary_key: Optional[str] = None, fallback_key: Optional[str] = None):
          self.primary_key = primary_key or os.getenv("PERPLEXITY_API_KEY")
          self.fallback_key = fallback_key or os.getenv("PERPLEXITY_API_KEY_FALLBACK")
          self.current_client = Perplexity(api_key=self.primary_key)
          self.logger = logging.getLogger(__name__)
      
      def _switch_to_fallback(self):
          """Switch to fallback API key if available"""
          if self.fallback_key:
              self.logger.warning("Switching to fallback API key")
              self.current_client = Perplexity(api_key=self.fallback_key)
              return True
          return False
      
      def search(self, query: str, **kwargs):
          try:
              return self.current_client.search.create(query=query, **kwargs)
          except Exception as e:
              if "authentication" in str(e).lower() and self._switch_to_fallback():
                  return self.current_client.search.create(query=query, **kwargs)
              raise e

  # Usage
  client = SecurePerplexityClient()
  ```

  ```typescript Typescript theme={null}
  import Perplexity from '@perplexity-ai/perplexity_ai';

  class SecurePerplexityClient {
      private primaryKey: string;
      private fallbackKey?: string;
      private currentClient: Perplexity;
      
      constructor(primaryKey?: string, fallbackKey?: string) {
          this.primaryKey = primaryKey || process.env.PERPLEXITY_API_KEY!;
          this.fallbackKey = fallbackKey || process.env.PERPLEXITY_API_KEY_FALLBACK;
          this.currentClient = new Perplexity({ apiKey: this.primaryKey });
      }
      
      private switchToFallback(): boolean {
          if (this.fallbackKey) {
              console.warn("Switching to fallback API key");
              this.currentClient = new Perplexity({ apiKey: this.fallbackKey });
              return true;
          }
          return false;
      }
      
      async search(query: string, options?: any) {
          try {
              return await this.currentClient.search.create({ query, ...options });
          } catch (error: any) {
              if (error.message.toLowerCase().includes('authentication') && this.switchToFallback()) {
                  return await this.currentClient.search.create({ query, ...options });
              }
              throw error;
          }
      }
  }

  // Usage
  const client = new SecurePerplexityClient();
  ```
</CodeGroup>

## Rate Limiting and Efficiency

### Intelligent Rate Limiting

Implement exponential backoff with jitter:

<CodeGroup>
  ```python Python theme={null}
  import time
  import random
  import asyncio
  from typing import TypeVar, Callable, Any
  import perplexity
  from perplexity import Perplexity

  T = TypeVar('T')

  class RateLimitedClient:
      def __init__(self, client: Perplexity, max_retries: int = 5):
          self.client = client
          self.max_retries = max_retries
      
      def _calculate_delay(self, attempt: int) -> float:
          """Calculate delay with exponential backoff and jitter"""
          base_delay = 2 ** attempt
          jitter = random.uniform(0.1, 0.5)
          return min(base_delay + jitter, 60.0)  # Cap at 60 seconds
      
      def with_retry(self, func: Callable[[], T]) -> T:
          """Execute function with intelligent retry logic"""
          last_exception = None
          
          for attempt in range(self.max_retries):
              try:
                  return func()
              except perplexity.RateLimitError as e:
                  last_exception = e
                  if attempt < self.max_retries - 1:
                      delay = self._calculate_delay(attempt)
                      print(f"Rate limited. Retrying in {delay:.2f}s (attempt {attempt + 1})")
                      time.sleep(delay)
                      continue
                  raise e
              except perplexity.APIConnectionError as e:
                  last_exception = e
                  if attempt < self.max_retries - 1:
                      delay = min(2 ** attempt, 10.0)  # Shorter delay for connection errors
                      print(f"Connection error. Retrying in {delay:.2f}s")
                      time.sleep(delay)
                      continue
                  raise e
          
          raise last_exception
      
      def search(self, query: str, **kwargs):
          return self.with_retry(
              lambda: self.client.search.create(query=query, **kwargs)
          )

  # Usage
  client = RateLimitedClient(Perplexity())
  result = client.search("artificial intelligence")
  ```

  ```typescript Typescript theme={null}
  import Perplexity from '@perplexity-ai/perplexity_ai';

  class RateLimitedClient {
      private client: Perplexity;
      private maxRetries: number;
      
      constructor(client: Perplexity, maxRetries: number = 5) {
          this.client = client;
          this.maxRetries = maxRetries;
      }
      
      private calculateDelay(attempt: number): number {
          const baseDelay = 2 ** attempt * 1000; // Convert to milliseconds
          const jitter = Math.random() * 500; // 0-500ms jitter
          return Math.min(baseDelay + jitter, 60000); // Cap at 60 seconds
      }
      
      async withRetry<T>(func: () => Promise<T>): Promise<T> {
          let lastError: any;
          
          for (let attempt = 0; attempt < this.maxRetries; attempt++) {
              try {
                  return await func();
              } catch (error: any) {
                  lastError = error;
                  
                  if (error.constructor.name === 'RateLimitError') {
                      if (attempt < this.maxRetries - 1) {
                          const delay = this.calculateDelay(attempt);
                          console.log(`Rate limited. Retrying in ${delay}ms (attempt ${attempt + 1})`);
                          await new Promise(resolve => setTimeout(resolve, delay));
                          continue;
                      }
                  } else if (error.constructor.name === 'APIConnectionError') {
                      if (attempt < this.maxRetries - 1) {
                          const delay = Math.min(2 ** attempt * 1000, 10000);
                          console.log(`Connection error. Retrying in ${delay}ms`);
                          await new Promise(resolve => setTimeout(resolve, delay));
                          continue;
                      }
                  }
                  
                  throw error;
              }
          }
          
          throw lastError;
      }
      
      async search(query: string, options?: any) {
          return this.withRetry(() => 
              this.client.search.create({ query, ...options })
          );
      }
  }

  // Usage
  const client = new RateLimitedClient(new Perplexity());
  const result = await client.search("artificial intelligence");
  ```
</CodeGroup>

### Request Batching

Efficiently batch multiple requests:

<CodeGroup>
  ```python Python theme={null}
  import asyncio
  from typing import List, TypeVar, Generic
  from perplexity import AsyncPerplexity, DefaultAioHttpClient

  T = TypeVar('T')

  class BatchProcessor(Generic[T]):
      def __init__(self, batch_size: int = 5, delay_between_batches: float = 1.0):
          self.batch_size = batch_size
          self.delay_between_batches = delay_between_batches
      
      async def process_batch(
          self, 
          items: List[str], 
          process_func: Callable[[str], Awaitable[T]]
      ) -> List[T]:
          """Process items in batches with rate limiting"""
          results = []
          
          for i in range(0, len(items), self.batch_size):
              batch = items[i:i + self.batch_size]
              
              # Process batch concurrently
              tasks = [process_func(item) for item in batch]
              batch_results = await asyncio.gather(*tasks, return_exceptions=True)
              
              # Filter out exceptions and collect results
              for result in batch_results:
                  if not isinstance(result, Exception):
                      results.append(result)
              
              # Delay between batches
              if i + self.batch_size < len(items):
                  await asyncio.sleep(self.delay_between_batches)
          
          return results

  # Usage
  async def main():
      processor = BatchProcessor(batch_size=3, delay_between_batches=0.5)
      
      async with AsyncPerplexity(
          http_client=DefaultAioHttpClient()
      ) as client:
          
          async def search_query(query: str):
              return await client.search.create(query=query)
          
          queries = ["AI", "ML", "DL", "NLP", "CV"]
          results = await processor.process_batch(queries, search_query)
          
          print(f"Processed {len(results)} successful queries")

  asyncio.run(main())
  ```

  ```typescript Typescript theme={null}
  import Perplexity from '@perplexity-ai/perplexity_ai';

  class BatchProcessor<T> {
      constructor(
          private batchSize: number = 5,
          private delayBetweenBatches: number = 1000
      ) {}
      
      async processBatch<R>(
          items: T[],
          processFunc: (item: T) => Promise<R>
      ): Promise<R[]> {
          const results: R[] = [];
          
          for (let i = 0; i < items.length; i += this.batchSize) {
              const batch = items.slice(i, i + this.batchSize);
              
              // Process batch concurrently
              const tasks = batch.map(item => 
                  processFunc(item).catch(error => error)
              );
              const batchResults = await Promise.all(tasks);
              
              // Filter out exceptions and collect results
              for (const result of batchResults) {
                  if (!(result instanceof Error)) {
                      results.push(result);
                  }
              }
              
              // Delay between batches
              if (i + this.batchSize < items.length) {
                  await new Promise(resolve => 
                      setTimeout(resolve, this.delayBetweenBatches)
                  );
              }
          }
          
          return results;
      }
  }

  // Usage
  async function main() {
      const processor = new BatchProcessor<string>(3, 500);
      const client = new Perplexity();
      
      const searchQuery = (query: string) => 
          client.search.create({ query });
      
      const queries = ["AI", "ML", "DL", "NLP", "CV"];
      const results = await processor.processBatch(queries, searchQuery);
      
      console.log(`Processed ${results.length} successful queries`);
  }

  main();
  ```
</CodeGroup>

## Production Configuration

### Configuration Management

Use environment-based configuration for different deployment stages:

<CodeGroup>
  ```python Python theme={null}
  import os
  from dataclasses import dataclass
  from typing import Optional
  import httpx
  from perplexity import Perplexity, DefaultHttpxClient

  @dataclass
  class PerplexityConfig:
      api_key: str
      max_retries: int = 3
      timeout_seconds: float = 30.0
      max_connections: int = 100
      max_keepalive: int = 20
      environment: str = "production"
      
      @classmethod
      def from_env(cls) -> "PerplexityConfig":
          """Load configuration from environment variables"""
          api_key = os.getenv("PERPLEXITY_API_KEY")
          if not api_key:
              raise ValueError("PERPLEXITY_API_KEY environment variable is required")
          
          return cls(
              api_key=api_key,
              max_retries=int(os.getenv("PERPLEXITY_MAX_RETRIES", "3")),
              timeout_seconds=float(os.getenv("PERPLEXITY_TIMEOUT", "30.0")),
              max_connections=int(os.getenv("PERPLEXITY_MAX_CONNECTIONS", "100")),
              max_keepalive=int(os.getenv("PERPLEXITY_MAX_KEEPALIVE", "20")),
              environment=os.getenv("ENVIRONMENT", "production")
          )
      
      def create_client(self) -> Perplexity:
          """Create optimized client based on configuration"""
          timeout = httpx.Timeout(
              connect=5.0,
              read=self.timeout_seconds,
              write=10.0,
              pool=10.0
          )
          
          limits = httpx.Limits(
              max_keepalive_connections=self.max_keepalive,
              max_connections=self.max_connections,
              keepalive_expiry=60.0 if self.environment == "production" else 30.0
          )
          
          return Perplexity(
              api_key=self.api_key,
              max_retries=self.max_retries,
              timeout=timeout,
              http_client=DefaultHttpxClient(limits=limits)
          )

  # Usage
  config = PerplexityConfig.from_env()
  client = config.create_client()
  ```

  ```typescript Typescript theme={null}
  import Perplexity from '@perplexity-ai/perplexity_ai';
  import https from 'https';

  interface PerplexityConfig {
      apiKey: string;
      maxRetries: number;
      timeoutMs: number;
      maxConnections: number;
      maxKeepalive: number;
      environment: string;
  }

  class ConfigManager {
      static fromEnv(): PerplexityConfig {
          const apiKey = process.env.PERPLEXITY_API_KEY;
          if (!apiKey) {
              throw new Error("PERPLEXITY_API_KEY environment variable is required");
          }
          
          return {
              apiKey,
              maxRetries: parseInt(process.env.PERPLEXITY_MAX_RETRIES || '3'),
              timeoutMs: parseInt(process.env.PERPLEXITY_TIMEOUT || '30000'),
              maxConnections: parseInt(process.env.PERPLEXITY_MAX_CONNECTIONS || '100'),
              maxKeepalive: parseInt(process.env.PERPLEXITY_MAX_KEEPALIVE || '20'),
              environment: process.env.NODE_ENV || 'production'
          };
      }
      
      static createClient(config: PerplexityConfig): Perplexity {
          const httpsAgent = new https.Agent({
              keepAlive: true,
              keepAliveMsecs: config.environment === 'production' ? 60000 : 30000,
              maxSockets: config.maxConnections,
              maxFreeSockets: config.maxKeepalive,
              timeout: config.timeoutMs
          });
          
          return new Perplexity({
              apiKey: config.apiKey,
              maxRetries: config.maxRetries,
              timeout: config.timeoutMs,
              httpAgent: httpsAgent
          });
      }
  }

  // Usage
  const config = ConfigManager.fromEnv();
  const client = ConfigManager.createClient(config);
  ```
</CodeGroup>

### Monitoring and Logging

Implement comprehensive monitoring:

<CodeGroup>
  ```python Python theme={null}
  import logging
  import time
  import functools
  from typing import Any, Callable
  from perplexity import Perplexity
  import perplexity

  # Configure logging
  logging.basicConfig(
      level=logging.INFO,
      format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
  )
  logger = logging.getLogger(__name__)

  class MonitoredPerplexityClient:
      def __init__(self, client: Perplexity):
          self.client = client
          self.request_count = 0
          self.error_count = 0
          self.total_response_time = 0.0
      
      def _log_request(self, method: str, **kwargs):
          """Log request details"""
          self.request_count += 1
          logger.info(f"Making {method} request #{self.request_count}")
          logger.debug(f"Request parameters: {kwargs}")
      
      def _log_response(self, method: str, duration: float, success: bool = True):
          """Log response details"""
          self.total_response_time += duration
          avg_response_time = self.total_response_time / self.request_count
          
          if success:
              logger.info(f"{method} completed in {duration:.2f}s (avg: {avg_response_time:.2f}s)")
          else:
              self.error_count += 1
              logger.error(f"{method} failed after {duration:.2f}s (errors: {self.error_count})")
      
      def search(self, query: str, **kwargs):
          self._log_request("search", query=query, **kwargs)
          start_time = time.time()
          
          try:
              result = self.client.search.create(query=query, **kwargs)
              duration = time.time() - start_time
              self._log_response("search", duration, success=True)
              return result
          except Exception as e:
              duration = time.time() - start_time
              self._log_response("search", duration, success=False)
              logger.error(f"Search error: {type(e).__name__}: {e}")
              raise
      
      def get_stats(self):
          """Get client statistics"""
          return {
              "total_requests": self.request_count,
              "error_count": self.error_count,
              "success_rate": (self.request_count - self.error_count) / max(self.request_count, 1),
              "avg_response_time": self.total_response_time / max(self.request_count, 1)
          }

  # Usage
  client = MonitoredPerplexityClient(Perplexity())
  result = client.search("machine learning")
  print(client.get_stats())
  ```

  ```typescript Typescript theme={null}
  import Perplexity from '@perplexity-ai/perplexity_ai';

  interface ClientStats {
      totalRequests: number;
      errorCount: number;
      successRate: number;
      avgResponseTime: number;
  }

  class MonitoredPerplexityClient {
      private client: Perplexity;
      private requestCount: number = 0;
      private errorCount: number = 0;
      private totalResponseTime: number = 0;
      
      constructor(client: Perplexity) {
          this.client = client;
      }
      
      private logRequest(method: string, params: any): void {
          this.requestCount++;
          console.log(`Making ${method} request #${this.requestCount}`);
          console.debug(`Request parameters:`, params);
      }
      
      private logResponse(method: string, duration: number, success: boolean = true): void {
          this.totalResponseTime += duration;
          const avgResponseTime = this.totalResponseTime / this.requestCount;
          
          if (success) {
              console.log(`${method} completed in ${duration.toFixed(2)}ms (avg: ${avgResponseTime.toFixed(2)}ms)`);
          } else {
              this.errorCount++;
              console.error(`${method} failed after ${duration.toFixed(2)}ms (errors: ${this.errorCount})`);
          }
      }
      
      async search(query: string, options?: any) {
          this.logRequest("search", { query, ...options });
          const startTime = performance.now();
          
          try {
              const result = await this.client.search.create({ query, ...options });
              const duration = performance.now() - startTime;
              this.logResponse("search", duration, true);
              return result;
          } catch (error) {
              const duration = performance.now() - startTime;
              this.logResponse("search", duration, false);
              console.error(`Search error: ${error}`);
              throw error;
          }
      }
      
      getStats(): ClientStats {
          return {
              totalRequests: this.requestCount,
              errorCount: this.errorCount,
              successRate: (this.requestCount - this.errorCount) / Math.max(this.requestCount, 1),
              avgResponseTime: this.totalResponseTime / Math.max(this.requestCount, 1)
          };
      }
  }

  // Usage
  const client = new MonitoredPerplexityClient(new Perplexity());
  const result = await client.search("machine learning");
  console.log(client.getStats());
  ```
</CodeGroup>

## Error Handling Best Practices

### Graceful Degradation

Implement fallback strategies for different error types:

<CodeGroup>
  ```python Python theme={null}
  from typing import Optional, Dict, Any
  import perplexity
  from perplexity import Perplexity

  class ResilientPerplexityClient:
      def __init__(self, client: Perplexity):
          self.client = client
          self.circuit_breaker_threshold = 5
          self.circuit_breaker_count = 0
          self.circuit_breaker_open = False
      
      def _should_circuit_break(self) -> bool:
          """Check if circuit breaker should be triggered"""
          return self.circuit_breaker_count >= self.circuit_breaker_threshold
      
      def _record_failure(self):
          """Record a failure for circuit breaker"""
          self.circuit_breaker_count += 1
          if self._should_circuit_break():
              self.circuit_breaker_open = True
              print("Circuit breaker activated - temporarily disabling API calls")
      
      def _record_success(self):
          """Record a success - reset circuit breaker"""
          self.circuit_breaker_count = 0
          self.circuit_breaker_open = False
      
      def search_with_fallback(
          self, 
          query: str, 
          fallback_response: Optional[Dict[str, Any]] = None
      ):
          """Search with graceful degradation"""
          if self.circuit_breaker_open:
              print("Circuit breaker open - returning fallback response")
              return fallback_response or {
                  "query": query,
                  "results": [],
                  "status": "service_unavailable"
              }
          
          try:
              result = self.client.search.create(query=query)
              self._record_success()
              return result
              
          except perplexity.RateLimitError:
              print("Rate limited - implementing backoff strategy")
              # Could implement intelligent backoff here
              raise
              
          except perplexity.APIConnectionError as e:
              print(f"Connection error: {e}")
              self._record_failure()
              return fallback_response or {
                  "query": query,
                  "results": [],
                  "status": "connection_error"
              }
              
          except Exception as e:
              print(f"Unexpected error: {e}")
              self._record_failure()
              return fallback_response or {
                  "query": query,
                  "results": [],
                  "status": "error"
              }

  # Usage
  client = ResilientPerplexityClient(Perplexity())
  result = client.search_with_fallback("machine learning")
  ```

  ```typescript Typescript theme={null}
  import Perplexity from '@perplexity-ai/perplexity_ai';

  interface FallbackResponse {
      query: string;
      results: any[];
      status: string;
  }

  class ResilientPerplexityClient {
      private client: Perplexity;
      private circuitBreakerThreshold: number = 5;
      private circuitBreakerCount: number = 0;
      private circuitBreakerOpen: boolean = false;
      
      constructor(client: Perplexity) {
          this.client = client;
      }
      
      private shouldCircuitBreak(): boolean {
          return this.circuitBreakerCount >= this.circuitBreakerThreshold;
      }
      
      private recordFailure(): void {
          this.circuitBreakerCount++;
          if (this.shouldCircuitBreak()) {
              this.circuitBreakerOpen = true;
              console.log("Circuit breaker activated - temporarily disabling API calls");
          }
      }
      
      private recordSuccess(): void {
          this.circuitBreakerCount = 0;
          this.circuitBreakerOpen = false;
      }
      
      async searchWithFallback(
          query: string,
          fallbackResponse?: FallbackResponse
      ): Promise<any> {
          if (this.circuitBreakerOpen) {
              console.log("Circuit breaker open - returning fallback response");
              return fallbackResponse || {
                  query,
                  results: [],
                  status: "service_unavailable"
              };
          }
          
          try {
              const result = await this.client.search.create({ query });
              this.recordSuccess();
              return result;
              
          } catch (error: any) {
              if (error.constructor.name === 'RateLimitError') {
                  console.log("Rate limited - implementing backoff strategy");
                  throw error;
              } else if (error.constructor.name === 'APIConnectionError') {
                  console.log(`Connection error: ${error.message}`);
                  this.recordFailure();
                  return fallbackResponse || {
                      query,
                      results: [],
                      status: "connection_error"
                  };
              } else {
                  console.log(`Unexpected error: ${error.message}`);
                  this.recordFailure();
                  return fallbackResponse || {
                      query,
                      results: [],
                      status: "error"
                  };
              }
          }
      }
  }

  // Usage
  const client = new ResilientPerplexityClient(new Perplexity());
  const result = await client.searchWithFallback("machine learning");
  ```
</CodeGroup>

## Testing Best Practices

### Unit Testing with Mocking

Create testable code with proper mocking:

<CodeGroup>
  ```python Python theme={null}
  import unittest
  from unittest.mock import Mock, patch
  from perplexity import Perplexity
  from perplexity.types import SearchCreateResponse, SearchResult

  class TestPerplexityIntegration(unittest.TestCase):
      def setUp(self):
          self.mock_client = Mock(spec=Perplexity)
          
      def test_search_success(self):
          # Mock successful response
          mock_result = SearchResult(
              title="Test Result",
              url="https://example.com",
              snippet="Test snippet"
          )
          
          mock_response = SearchCreateResponse(
              query="test query",
              results=[mock_result]
          )
          
          self.mock_client.search.create.return_value = mock_response
          
          # Test your application logic
          result = self.mock_client.search.create(query="test query")
          
          self.assertEqual(result.query, "test query")
          self.assertEqual(len(result.results), 1)
          self.assertEqual(result.results[0].title, "Test Result")
      
      @patch('perplexity.Perplexity')
      def test_rate_limit_handling(self, mock_perplexity_class):
          # Mock rate limit error
          mock_client = Mock()
          mock_perplexity_class.return_value = mock_client
          mock_client.search.create.side_effect = perplexity.RateLimitError("Rate limited")
          
          # Test your error handling logic here
          with self.assertRaises(perplexity.RateLimitError):
              mock_client.search.create(query="test")

  if __name__ == '__main__':
      unittest.main()
  ```

  ```typescript Typescript theme={null}
  import { jest } from '@jest/globals';
  import Perplexity from '@perplexity-ai/perplexity_ai';
  import type { SearchCreateResponse, SearchResult } from '@perplexity-ai/perplexity_ai';

  // Mock the Perplexity client
  jest.mock('@perplexity-ai/perplexity_ai');

  describe('Perplexity Integration', () => {
      let mockClient: jest.Mocked<Perplexity>;
      
      beforeEach(() => {
          mockClient = new Perplexity() as jest.Mocked<Perplexity>;
      });
      
      test('should handle successful search', async () => {
          const mockResult: SearchResult = {
              title: "Test Result",
              url: "https://example.com",
              snippet: "Test snippet"
          };
          
          const mockResponse: SearchCreateResponse = {
              query: "test query",
              results: [mockResult]
          };
          
          (mockClient.search.create as jest.Mock).mockResolvedValue(mockResponse);
          
          const result = await mockClient.search.create({ query: "test query" });
          
          expect(result.query).toBe("test query");
          expect(result.results).toHaveLength(1);
          expect(result.results[0].title).toBe("Test Result");
      });
      
      test('should handle rate limit errors', async () => {
          const rateLimitError = new Error('Rate limited');
          rateLimitError.constructor.name = 'RateLimitError';
          
          (mockClient.search.create as jest.Mock).mockRejectedValue(rateLimitError);
          
          await expect(mockClient.search.create({ query: "test" })).rejects.toThrow('Rate limited');
      });
  });
  ```
</CodeGroup>

## Performance Best Practices Summary

<Steps>
  <Step title="Use environment variables for configuration">
    Never hardcode API keys or configuration values.
  </Step>

  <Step title="Implement intelligent rate limiting">
    Use exponential backoff with jitter for retry strategies.
  </Step>

  <Step title="Configure connection pooling">
    Optimize HTTP client settings for your use case.
  </Step>

  <Step title="Monitor and log appropriately">
    Track performance metrics and error rates.
  </Step>

  <Step title="Implement graceful degradation">
    Provide fallback responses when APIs are unavailable.
  </Step>

  <Step title="Write testable code">
    Use dependency injection and mocking for unit tests.
  </Step>
</Steps>

## Related Resources

<CardGroup cols={2}>
  <Card title="Error Handling" icon="alert-triangle" href="/docs/sdk/error-handling">
    Comprehensive error handling strategies
  </Card>

  <Card title="Performance" icon="bolt" href="/docs/sdk/performance">
    Async operations and optimization techniques
  </Card>

  <Card title="Configuration" icon="settings" href="/docs/sdk/configuration">
    Production-ready configuration patterns
  </Card>

  <Card title="Type Safety" icon="shield-check" href="/docs/sdk/type-safety">
    Leveraging types for safer code
  </Card>
</CardGroup>
