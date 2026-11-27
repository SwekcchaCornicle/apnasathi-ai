import { AuthenticationDetails, CognitoUser, CognitoUserPool } from 'amazon-cognito-identity-js'

export function signInWithSrp({ userPoolId, clientId, email, password }) {
  // The application handles its session storage. Keep the SDK session in memory.
  const values = new Map()
  const storage = {
    getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, value),
    removeItem: (key) => values.delete(key),
    clear: () => values.clear(),
  }
  const pool = new CognitoUserPool({ UserPoolId: userPoolId, ClientId: clientId, Storage: storage })
  const user = new CognitoUser({ Username: email, Pool: pool, Storage: storage })
  const details = new AuthenticationDetails({ Username: email, Password: password })
  user.setAuthenticationFlowType('USER_SRP_AUTH')

  return new Promise((resolve, reject) => {
    const unsupportedChallenge = () => reject(new Error('This account requires an additional sign-in step.'))
    user.authenticateUser(details, {
      onSuccess: (session) => resolve(session.getIdToken().getJwtToken()),
      onFailure: reject,
      newPasswordRequired: unsupportedChallenge,
      mfaRequired: unsupportedChallenge,
      totpRequired: unsupportedChallenge,
      mfaSetup: unsupportedChallenge,
      selectMFAType: unsupportedChallenge,
      customChallenge: unsupportedChallenge,
    })
  })
}
