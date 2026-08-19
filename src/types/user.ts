export interface Usuario {
  id: string;
  email: string;
  passwordHash: string;
  salt: string;
  creadoEn: string;
}

export interface SesionPayload {
  uid: string;
  email: string;
}
