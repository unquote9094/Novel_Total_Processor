> ## Documentation Index
> Fetch the complete documentation index at: https://docs.perplexity.ai/llms.txt
> Use this file to discover all available pages before exploring further.

# Search the Web

> Search the web and retrieve relevant web page contents.



## OpenAPI

````yaml post /search
openapi: 3.1.0
info:
  title: Perplexity AI API
  description: Perplexity AI API
  version: 1.0.0
servers:
  - url: https://api.perplexity.ai
    description: Perplexity AI API
security: []
paths:
  /search:
    post:
      summary: Search the Web
      description: Search the web and retrieve relevant web page contents.
      operationId: search_search_post
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/ApiSearchRequest'
      responses:
        '200':
          description: Successful Response
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ApiSearchResponse'
        '422':
          description: Validation Error
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/HTTPValidationError'
      security:
        - HTTPBearer: []
components:
  schemas:
    ApiSearchRequest:
      properties:
        query:
          anyOf:
            - type: string
            - items:
                type: string
              type: array
          title: Query
        max_tokens:
          type: integer
          title: Max Tokens
          default: 10000
        max_tokens_per_page:
          type: integer
          title: Max Tokens Per Page
          default: 4096
        max_results:
          type: integer
          title: Max Results
          default: 10
        search_domain_filter:
          anyOf:
            - items:
                type: string
              type: array
            - type: 'null'
          title: Search Domain Filter
        search_language_filter:
          anyOf:
            - items:
                type: string
              type: array
            - type: 'null'
          title: Search Language Filter
        search_recency_filter:
          anyOf:
            - type: string
              enum:
                - hour
                - day
                - week
                - month
                - year
            - type: 'null'
          title: Search Recency Filter
        search_after_date_filter:
          anyOf:
            - type: string
            - type: 'null'
          title: Search After Date Filter
        search_before_date_filter:
          anyOf:
            - type: string
            - type: 'null'
          title: Search Before Date Filter
        last_updated_before_filter:
          anyOf:
            - type: string
            - type: 'null'
          title: Last Updated Before Filter
        last_updated_after_filter:
          anyOf:
            - type: string
            - type: 'null'
          title: Last Updated After Filter
        search_mode:
          anyOf:
            - type: string
              enum:
                - web
                - academic
                - sec
            - type: 'null'
          title: Search Mode
        country:
          anyOf:
            - type: string
            - type: 'null'
          title: Country
        display_server_time:
          type: boolean
          title: Display Server Time
          default: false
      type: object
      required:
        - query
      title: ApiSearchRequest
    ApiSearchResponse:
      properties:
        results:
          items:
            $ref: '#/components/schemas/ApiSearchPage'
          type: array
          title: Results
        id:
          type: string
          title: Id
        server_time:
          anyOf:
            - type: string
            - type: 'null'
          title: Server Time
      type: object
      required:
        - results
        - id
      title: ApiSearchResponse
    HTTPValidationError:
      properties:
        detail:
          items:
            $ref: '#/components/schemas/ValidationError'
          type: array
          title: Detail
      type: object
      title: HTTPValidationError
    ApiSearchPage:
      properties:
        title:
          type: string
          title: Title
        url:
          type: string
          title: Url
        snippet:
          type: string
          title: Snippet
        date:
          anyOf:
            - type: string
            - type: 'null'
          title: Date
        last_updated:
          anyOf:
            - type: string
            - type: 'null'
          title: Last Updated
      type: object
      required:
        - title
        - url
        - snippet
      title: ApiSearchPage
    ValidationError:
      properties:
        loc:
          items:
            anyOf:
              - type: string
              - type: integer
          type: array
          title: Location
        msg:
          type: string
          title: Message
        type:
          type: string
          title: Error Type
      type: object
      required:
        - loc
        - msg
        - type
      title: ValidationError
  securitySchemes:
    HTTPBearer:
      type: http
      scheme: bearer

````



================================================================


> ## Documentation Index
> Fetch the complete documentation index at: https://docs.perplexity.ai/llms.txt
> Use this file to discover all available pages before exploring further.

# Best Practices

> Learn best practices for optimizing search queries and implementing efficient async patterns with Perplexity's Search API.

***

## Overview

This guide covers essential best practices for getting the most out of Perplexity's Search API, including query optimization techniques and efficient async usage patterns for high-performance applications.

## Query Optimization

<Steps>
  <Step title="Write specific queries">
    Use highly specific queries for more targeted results. For example, instead of searching for "AI", use a detailed query like "artificial intelligence machine learning healthcare applications 2024".

    <CodeGroup>
      ```python Python theme={null}
      # Better: Specific query
      search = client.search.create(
          query="artificial intelligence medical diagnosis accuracy 2024",
          max_results=10
      )

      # Avoid: Vague query
      search = client.search.create(
          query="AI medical",
          max_results=10
      )
      ```

      ```typescript Typescript theme={null}
      // Better: Specific query
      const search = await client.search.create({
          query: "artificial intelligence medical diagnosis accuracy 2024",
          maxResults: 10
      });

      // Avoid: Vague query
      const search = await client.search.create({
          query: "AI medical",
          maxResults: 10
      });
      ```
    </CodeGroup>

    <Tip>
      Specific queries with context, time frames, and precise terminology yield more relevant and actionable results.
    </Tip>
  </Step>

  <Step title="Use multi-query for comprehensive research">
    Break your main topic into related sub-queries to cover all aspects of your research. Use the multi-query search feature to run multiple related queries in a single request for more comprehensive and relevant information.

    <CodeGroup>
      ```python Python theme={null}
      from perplexity import Perplexity

      client = Perplexity()

      # Comprehensive research with related queries
      search = client.search.create(
          query=[
              "artificial intelligence medical diagnosis accuracy 2024",
              "machine learning healthcare applications FDA approval",
              "AI medical imaging radiology deployment hospitals"
          ],
          max_results=5
      )

      # Access results for each query
      for i, query_results in enumerate(search.results):
          print(f"Results for query {i+1}:")
          for result in query_results:
              print(f"  {result.title}: {result.url}")
          print("---")
      ```

      ```typescript Typescript theme={null}
      import Perplexity from '@perplexity-ai/perplexity_ai';

      const client = new Perplexity();

      // Comprehensive research with related queries
      const search = await client.search.create({
          query: [
              "artificial intelligence medical diagnosis accuracy 2024",
              "machine learning healthcare applications FDA approval",
              "AI medical imaging radiology deployment hospitals"
          ],
          maxResults: 5
      });

      // Access results for each query
      search.results.forEach((queryResults, i) => {
          console.log(`Results for query ${i+1}:`);
          queryResults.forEach(result => {
              console.log(`  ${result.title}: ${result.url}`);
          });
          console.log("---");
      });
      ```
    </CodeGroup>

    <Info>
      You can include up to 5 queries in a single multi-query request for efficient batch processing.
    </Info>
  </Step>

  <Step title="Handle rate limits efficiently">
    Implement exponential backoff for rate limit errors and use appropriate batching strategies.

    <CodeGroup>
      ```python Python theme={null}
      import time
      import random
      from perplexity import RateLimitError

      def search_with_retry(client, query, max_retries=3):
          for attempt in range(max_retries):
              try:
                  return client.search.create(query=query)
              except RateLimitError:
                  if attempt < max_retries - 1:
                      # Exponential backoff with jitter
                      delay = (2 ** attempt) + random.uniform(0, 1)
                      time.sleep(delay)
                  else:
                      raise

      # Usage
      try:
          search = search_with_retry(client, "AI developments")
          for result in search.results:
              print(f"{result.title}: {result.url}")
      except RateLimitError:
          print("Maximum retries exceeded for search")
      ```

      ```typescript Typescript theme={null}
      import Perplexity from '@perplexity-ai/perplexity_ai';

      async function searchWithRetry(
          client: Perplexity, 
          query: string, 
          maxRetries: number = 3
      ) {
          for (let attempt = 0; attempt < maxRetries; attempt++) {
              try {
                  return await client.search.create({ query });
              } catch (error) {
                  if (error instanceof Perplexity.RateLimitError && attempt < maxRetries - 1) {
                      // Exponential backoff with jitter
                      const delay = (2 ** attempt) + Math.random();
                      await new Promise(resolve => setTimeout(resolve, delay * 1000));
                  } else {
                      throw error;
                  }
              }
          }
          throw new Error("Max retries exceeded");
      }

      // Usage
      try {
          const search = await searchWithRetry(client, "AI developments");
          search.results.forEach(result => {
              console.log(`${result.title}: ${result.url}`);
          });
      } catch (error) {
          console.log("Maximum retries exceeded for search");
      }
      ```
    </CodeGroup>
  </Step>

  <Step title="Process concurrent searches efficiently">
    Use async for concurrent requests while respecting rate limits.

    <CodeGroup>
      ```python Python theme={null}
      import asyncio
      from perplexity import AsyncPerplexity

      async def batch_search(queries, batch_size=3, delay_ms=1000):
          async with AsyncPerplexity() as client:
              results = []
              
              for i in range(0, len(queries), batch_size):
                  batch = queries[i:i + batch_size]
                  
                  batch_tasks = [
                      client.search.create(query=query, max_results=5)
                      for query in batch
                  ]
                  
                  batch_results = await asyncio.gather(*batch_tasks)
                  results.extend(batch_results)
                  
                  # Add delay between batches
                  if i + batch_size < len(queries):
                      await asyncio.sleep(delay_ms / 1000)
              
              return results

      # Usage
      queries = ["AI developments", "climate change", "space exploration"]
      results = asyncio.run(batch_search(queries))
      print(f"Processed {len(results)} searches")
      ```

      ```typescript Typescript theme={null}
      import Perplexity from '@perplexity-ai/perplexity_ai';

      async function batchSearch(
          queries: string[],
          batchSize: number = 3,
          delayMs: number = 1000
      ) {
          const client = new Perplexity();
          const results = [];
          
          for (let i = 0; i < queries.length; i += batchSize) {
              const batch = queries.slice(i, i + batchSize);
              
              const batchPromises = batch.map(query =>
                  client.search.create({
                      query,
                      maxResults: 5
                  })
              );
              
              const batchResults = await Promise.all(batchPromises);
              results.push(...batchResults);
              
              // Add delay between batches
              if (i + batchSize < queries.length) {
                  await new Promise(resolve => setTimeout(resolve, delayMs));
              }
          }
          
          return results;
      }

      // Usage
      const queries = ["AI developments", "climate change", "space exploration"];
      const results = await batchSearch(queries);
      console.log(`Processed ${results.length} searches`);
      ```
    </CodeGroup>
  </Step>
</Steps>

## Async Usage

For high-performance applications requiring concurrent requests, use the async client:

<CodeGroup>
  ```python Python theme={null}
  import asyncio
  from perplexity import AsyncPerplexity

  async def main():
      async with AsyncPerplexity() as client:
          # Concurrent searches for better performance
          tasks = [
              client.search.create(
                  query="artificial intelligence trends 2024",
                  max_results=5
              ),
              client.search.create(
                  query="machine learning breakthroughs",
                  max_results=5
              ),
              client.search.create(
                  query="deep learning applications",
                  max_results=5
              )
          ]
          
          results = await asyncio.gather(*tasks)
          
          for i, search in enumerate(results):
              print(f"Query {i+1} results:")
              for result in search.results:
                  print(f"  {result.title}: {result.url}")
              print("---")

  asyncio.run(main())
  ```

  ```typescript Typescript theme={null}
  import Perplexity from '@perplexity-ai/perplexity_ai';

  const client = new Perplexity();

  async function main() {
      // Concurrent searches for better performance
      const tasks = [
          client.search.create({
              query: "artificial intelligence trends 2024",
              maxResults: 5
          }),
          client.search.create({
              query: "machine learning breakthroughs",
              maxResults: 5
          }),
          client.search.create({
              query: "deep learning applications",
              maxResults: 5
          })
      ];
      
      const results = await Promise.all(tasks);
      
      results.forEach((search, i) => {
          console.log(`Query ${i+1} results:`);
          search.results.forEach(result => {
              console.log(`  ${result.title}: ${result.url}`);
          });
          console.log("---");
      });
  }

  main();
  ```

  ```javascript JavaScript theme={null}
  const Perplexity = require('@perplexity-ai/perplexity_ai');

  const client = new Perplexity();

  async function main() {
      // Concurrent searches for better performance
      const tasks = [
          client.search.create({
              query: "artificial intelligence trends 2024",
              maxResults: 5
          }),
          client.search.create({
              query: "machine learning breakthroughs",
              maxResults: 5
          }),
          client.search.create({
              query: "deep learning applications",
              maxResults: 5
          })
      ];
      
      const results = await Promise.all(tasks);
      
      results.forEach((search, i) => {
          console.log(`Query ${i+1} results:`);
          search.results.forEach(result => {
              console.log(`  ${result.title}: ${result.url}`);
          });
          console.log("---");
      });
  }

  main();
  ```
</CodeGroup>

### Advanced Async Patterns

#### Rate-Limited Concurrent Processing

For large-scale applications, implement controlled concurrency with rate limiting:

<CodeGroup>
  ```python Python theme={null}
  import asyncio
  from perplexity import AsyncPerplexity

  class SearchManager:
      def __init__(self, max_concurrent=5, delay_between_batches=1.0):
          self.max_concurrent = max_concurrent
          self.delay_between_batches = delay_between_batches
          self.semaphore = asyncio.Semaphore(max_concurrent)
      
      async def search_single(self, client, query):
          async with self.semaphore:
              return await client.search.create(query=query, max_results=5)
      
      async def search_many(self, queries):
          async with AsyncPerplexity() as client:
              tasks = [
                  self.search_single(client, query) 
                  for query in queries
              ]
              
              results = await asyncio.gather(*tasks, return_exceptions=True)
              
              # Filter out exceptions and return successful results
              successful_results = [
                  result for result in results 
                  if not isinstance(result, Exception)
              ]
              
              return successful_results

  # Usage
  async def main():
      manager = SearchManager(max_concurrent=3)
      queries = [
          "AI research 2024",
          "quantum computing advances",
          "renewable energy innovations",
          "biotechnology breakthroughs",
          "space exploration updates"
      ]
      
      results = await manager.search_many(queries)
      print(f"Successfully processed {len(results)} out of {len(queries)} searches")

  asyncio.run(main())
  ```

  ```typescript Typescript theme={null}
  import Perplexity from '@perplexity-ai/perplexity_ai';

  class SearchManager {
      private maxConcurrent: number;
      private delayBetweenBatches: number;
      
      constructor(maxConcurrent: number = 5, delayBetweenBatches: number = 1000) {
          this.maxConcurrent = maxConcurrent;
          this.delayBetweenBatches = delayBetweenBatches;
      }
      
      async searchMany(queries: string[]) {
          const client = new Perplexity();
          const results = [];
          
          // Process in batches to respect rate limits
          for (let i = 0; i < queries.length; i += this.maxConcurrent) {
              const batch = queries.slice(i, i + this.maxConcurrent);
              
              const batchPromises = batch.map(query =>
                  client.search.create({ query, maxResults: 5 })
                      .catch(error => ({ error, query }))
              );
              
              const batchResults = await Promise.all(batchPromises);
              
              // Filter out errors and collect successful results
              const successfulResults = batchResults.filter(
                  result => !('error' in result)
              );
              
              results.push(...successfulResults);
              
              // Add delay between batches
              if (i + this.maxConcurrent < queries.length) {
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
      const manager = new SearchManager(3, 1000);
      const queries = [
          "AI research 2024",
          "quantum computing advances", 
          "renewable energy innovations",
          "biotechnology breakthroughs",
          "space exploration updates"
      ];
      
      const results = await manager.searchMany(queries);
      console.log(`Successfully processed ${results.length} out of ${queries.length} searches`);
  }

  main();
  ```
</CodeGroup>

#### Error Handling in Async Operations

Implement robust error handling for async search operations:

<CodeGroup>
  ```python Python theme={null}
  import asyncio
  import logging
  from perplexity import AsyncPerplexity, APIStatusError, RateLimitError

  logging.basicConfig(level=logging.INFO)
  logger = logging.getLogger(__name__)

  async def resilient_search(client, query, max_retries=3):
      for attempt in range(max_retries):
          try:
              result = await client.search.create(query=query, max_results=5)
              logger.info(f"Search successful for: {query}")
              return result
              
          except RateLimitError as e:
              if attempt < max_retries - 1:
                  delay = 2 ** attempt
                  logger.warning(f"Rate limited for '{query}', retrying in {delay}s")
                  await asyncio.sleep(delay)
              else:
                  logger.error(f"Max retries exceeded for: {query}")
                  return None
                  
          except APIStatusError as e:
              logger.error(f"API error for '{query}': {e}")
              return None
              
          except Exception as e:
              logger.error(f"Unexpected error for '{query}': {e}")
              return None

  async def main():
      async with AsyncPerplexity() as client:
          queries = ["AI developments", "invalid query", "tech trends"]
          
          tasks = [resilient_search(client, query) for query in queries]
          results = await asyncio.gather(*tasks)
          
          successful_results = [r for r in results if r is not None]
          print(f"Successful searches: {len(successful_results)}/{len(queries)}")

  asyncio.run(main())
  ```

  ```typescript Typescript theme={null}
  import Perplexity from '@perplexity-ai/perplexity_ai';

  async function resilientSearch(
      client: Perplexity, 
      query: string, 
      maxRetries: number = 3
  ) {
      for (let attempt = 0; attempt < maxRetries; attempt++) {
          try {
              const result = await client.search.create({ query, maxResults: 5 });
              console.log(`Search successful for: ${query}`);
              return result;
              
          } catch (error: any) {
              if (error.constructor.name === 'RateLimitError') {
                  if (attempt < maxRetries - 1) {
                      const delay = 2 ** attempt * 1000;
                      console.warn(`Rate limited for '${query}', retrying in ${delay}ms`);
                      await new Promise(resolve => setTimeout(resolve, delay));
                  } else {
                      console.error(`Max retries exceeded for: ${query}`);
                      return null;
                  }
              } else {
                  console.error(`Error for '${query}':`, error.message);
                  return null;
              }
          }
      }
      
      return null;
  }

  async function main() {
      const client = new Perplexity();
      const queries = ["AI developments", "invalid query", "tech trends"];
      
      const tasks = queries.map(query => resilientSearch(client, query));
      const results = await Promise.all(tasks);
      
      const successfulResults = results.filter(r => r !== null);
      console.log(`Successful searches: ${successfulResults.length}/${queries.length}`);
  }

  main();
  ```
</CodeGroup>

## Performance Optimization Tips

<Steps>
  <Step title="Optimize result count">
    Request only the number of results you actually need. More results = longer response times.

    ```python  theme={null}
    # Good: Request only what you need
    search = client.search.create(query="tech news", max_results=5)

    # Avoid: Over-requesting results
    search = client.search.create(query="tech news", max_results=50)
    ```
  </Step>

  <Step title="Cache frequently used searches">
    Implement caching for queries that don't need real-time results.

    <CodeGroup>
      ```python Python theme={null}
      import time
      from typing import Dict, Tuple, Optional

      class SearchCache:
          def __init__(self, ttl_seconds=3600):  # 1 hour default
              self.cache: Dict[str, Tuple[any, float]] = {}
              self.ttl = ttl_seconds
          
          def get(self, query: str) -> Optional[any]:
              if query in self.cache:
                  result, timestamp = self.cache[query]
                  if time.time() - timestamp < self.ttl:
                      return result
                  else:
                      del self.cache[query]
              return None
          
          def set(self, query: str, result: any):
              self.cache[query] = (result, time.time())

      # Usage
      cache = SearchCache(ttl_seconds=1800)  # 30 minutes

      def cached_search(client, query):
          cached_result = cache.get(query)
          if cached_result:
              return cached_result
          
          result = client.search.create(query=query)
          cache.set(query, result)
          return result
      ```

      ```typescript Typescript theme={null}
      class SearchCache {
          private cache: Map<string, { result: any; timestamp: number }> = new Map();
          private ttl: number;
          
          constructor(ttlSeconds: number = 3600) {  // 1 hour default
              this.ttl = ttlSeconds * 1000;  // Convert to milliseconds
          }
          
          get(query: string): any | null {
              const cached = this.cache.get(query);
              if (cached) {
                  if (Date.now() - cached.timestamp < this.ttl) {
                      return cached.result;
                  } else {
                      this.cache.delete(query);
                  }
              }
              return null;
          }
          
          set(query: string, result: any): void {
              this.cache.set(query, { result, timestamp: Date.now() });
          }
      }

      // Usage
      const cache = new SearchCache(1800);  // 30 minutes

      async function cachedSearch(client: Perplexity, query: string) {
          const cachedResult = cache.get(query);
          if (cachedResult) {
              return cachedResult;
          }
          
          const result = await client.search.create({ query });
          cache.set(query, result);
          return result;
      }
      ```
    </CodeGroup>
  </Step>
</Steps>

## Related Resources

<CardGroup cols={2}>
  <Card title="Quickstart" icon="rocket" href="/docs/search/quickstart">
    Get started with basic search functionality
  </Card>

  <Card title="Perplexity SDK" icon="code-circle" href="/docs/sdk/overview">
    Explore the full SDK capabilities for enhanced performance
  </Card>

  <Card title="API Reference" icon="book" href="/api-reference/search-post">
    Complete Search API documentation
  </Card>
</CardGroup>



