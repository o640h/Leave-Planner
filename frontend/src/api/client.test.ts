import { expect, it } from 'vitest'

import { ApiClientError, operatorErrorMessage } from './client'

it('shows the useful field reason from an API validation response', () => {
  const error = new ApiClientError(422, 'validation_error', 'Request validation failed', [
    {
      loc: ['body', 'cycle_anchor_date'],
      msg: 'Value error, The cycle anchor cannot be after Effective From',
    },
  ])

  expect(operatorErrorMessage(error)).toBe(
    'cycle anchor date: The cycle anchor cannot be after Effective From',
  )
})
