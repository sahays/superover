/* eslint-disable */
/* tslint:disable */

/**
 * Mock Service Worker (2.3.4).
 * @see https://github.com/mswjs/msw
 * - Please do NOT modify this file.
 * - Please do NOT serve this file on production.
 */

const INTEGRITY_CHECKSUM = '7e7b76fb9e80bb0d8b4a0b3d3b4f7d3a'
const IS_MOCKED_RESPONSE = Symbol('isMockedResponse')
const activeClientIds = new Set()

self.addEventListener('install', function () {
  self.skipWaiting()
})

self.addEventListener('activate', function (event) {
  event.waitUntil(self.clients.claim())
})

self.addEventListener('message', async function (event) {
  const clientId = event.source.id

  if (!clientId || !event.data) {
    return
  }

  const allClients = await self.clients.matchAll({
    type: 'window',
  })

  switch (event.data.type) {
    case 'KEEPALIVE_REQUEST': {
      sendToClient(event.source, {
        type: 'KEEPALIVE_RESPONSE',
      })
      break
    }

    case 'INTEGRITY_CHECK_REQUEST': {
      sendToClient(event.source, {
        type: 'INTEGRITY_CHECK_RESPONSE',
        payload: INTEGRITY_CHECKSUM,
      })
      break
    }

    case 'MOCK_ACTIVATE': {
      activeClientIds.add(clientId)

      sendToClient(event.source, {
        type: 'MOCKING_ENABLED',
      })
      break
    }

    case 'MOCK_DEACTIVATE': {
      activeClientIds.delete(clientId)
      break
    }

    case 'CLIENT_CLOSED': {
      activeClientIds.delete(clientId)

      const remainingClients = allClients.filter((client) => {
        return client.id !== clientId
      })

      // Unregister itself when there are no more clients
      if (remainingClients.length === 0) {
        self.registration.unregister()
      }

      break
    }
  }
})

self.addEventListener('fetch', function (event) {
  const { request } = event

  // Bypass service worker for non-GET requests
  if (request.method !== 'GET') {
    return
  }

  // Bypass service worker for requests that don't match the base path
  if (!request.url.startsWith(self.location.origin)) {
    return
  }

  // Get the client that issued this request
  event.respondWith(
    handleRequest(event, request)
  )
})

async function handleRequest(event, request) {
  const client = await event.target.clients.get(event.clientId)

  if (
    // Bypass mocking when the client is not active
    !client ||
    !activeClientIds.has(client.id)
  ) {
    return fetch(request)
  }

  // Bypass mocking for the actual mockServiceWorker script
  if (request.url.endsWith('/mockServiceWorker.js')) {
    return fetch(request)
  }

  return fetch(request)
}

function sendToClient(client, message) {
  return new Promise((resolve, reject) => {
    const channel = new MessageChannel()

    channel.port1.onmessage = (event) => {
      if (event.data.error) {
        return reject(event.data.error)
      }

      resolve(event.data)
    }

    client.postMessage(message, [channel.port2])
  })
}