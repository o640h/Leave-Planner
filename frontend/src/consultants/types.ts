export type Consultant = {
  id: number
  name: string
  post_title: string | null
}

export type ConsultantInput = {
  name: string
  post_title: string | null
}

export const emptyConsultantInput = (): ConsultantInput => ({
  name: '',
  post_title: null,
})
