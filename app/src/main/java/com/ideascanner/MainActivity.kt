package com.ideascanner

import android.content.Intent
import android.os.Bundle
import android.util.Log
import android.widget.Toast
import androidx.activity.result.ActivityResultLauncher
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import com.android.billingclient.api.*
import com.ideascanner.databinding.ActivityMainBinding
import com.google.android.gms.auth.api.signin.GoogleSignIn
import com.google.android.gms.auth.api.signin.GoogleSignInAccount
import com.google.android.gms.auth.api.signin.GoogleSignInOptions
import com.google.android.gms.common.api.ApiException
import retrofit2.Call
import retrofit2.Callback
import retrofit2.Response

class MainActivity : AppCompatActivity(), PurchasesUpdatedListener {
    private lateinit var binding: ActivityMainBinding

    // Google Sign-in
    private lateinit var googleSignInLauncher: ActivityResultLauncher<Intent>
    private val RC_SIGN_IN = 1001

    // Billing
    private lateinit var billingClient: BillingClient
    private val SKU_ID = "ideacredit_10" // <-- Replace with your SKU id in Play Console
    private val PACKAGE_NAME = "com.ideascanner"

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)

        setupGoogleSignInLauncher()
        initBillingClient()

        binding.btnGoogleSignIn.setOnClickListener {
            startGoogleSignIn()
        }

        binding.btnPurchase.setOnClickListener {
            startPurchaseFlow()
        }

        // If you want auto-login check:
        val acct = GoogleSignIn.getLastSignedInAccount(this)
        acct?.let { updateUiAfterSignIn(it) }
    }

    // -------------------------
    // Google Sign-In
    // -------------------------
    private fun setupGoogleSignInLauncher() {
        googleSignInLauncher = registerForActivityResult(
            ActivityResultContracts.StartActivityForResult()
        ) { result ->
            try {
                val task = GoogleSignIn.getSignedInAccountFromIntent(result.data)
                val account = task.getResult(ApiException::class.java)
                handleGoogleAccount(account)
            } catch (e: ApiException) {
                Log.w("MainActivity", "Google sign-in failed: ${e.statusCode}")
                Toast.makeText(this, "Google sign-in failed", Toast.LENGTH_SHORT).show()
            }
        }
    }

    private fun startGoogleSignIn() {
        // NOTE: Add your web client ID into strings.xml (see below) and replace R.string.default_web_client_id
        val gso = GoogleSignInOptions.Builder(GoogleSignInOptions.DEFAULT_SIGN_IN)
            .requestEmail()
            .requestId() // returns Google id
            .requestIdToken(getString(R.string.default_web_client_id)) // <-- needed for backend verification if required
            .build()
        val client = GoogleSignIn.getClient(this, gso)
        googleSignInLauncher.launch(client.signInIntent)
    }

    private fun handleGoogleAccount(account: GoogleSignInAccount?) {
        if (account == null) {
            Toast.makeText(this, "Google account is null", Toast.LENGTH_SHORT).show()
            return
        }
        updateUiAfterSignIn(account)

        // Send basic info to backend to create/login user and obtain JWT token
        val body = mapOf(
            "email" to (account.email ?: ""),
            "google_id" to (account.id ?: ""),
            "location" to "" // optional: get from UI
        )
        ApiClient.instance.googleLogin(body).enqueue(object: Callback<AuthResponse> {
            override fun onResponse(call: Call<AuthResponse>, response: Response<AuthResponse>) {
                val b = response.body()
                if (b != null && b.ok && b.access_token != null) {
                    Storage.saveToken(this@MainActivity, b.access_token)
                    Toast.makeText(this@MainActivity, "Logged in", Toast.LENGTH_SHORT).show()
                } else {
                    Toast.makeText(this@MainActivity, "Backend login failed", Toast.LENGTH_SHORT).show()
                }
            }
            override fun onFailure(call: Call<AuthResponse>, t: Throwable) {
                Toast.makeText(this@MainActivity, "Network error: ${t.localizedMessage}", Toast.LENGTH_SHORT).show()
            }
        })
    }

    private fun updateUiAfterSignIn(account: GoogleSignInAccount) {
        binding.tvStatus.text = "Signed in: ${account.email}"
    }

    // -------------------------
    // Billing
    // -------------------------
    private fun initBillingClient() {
        billingClient = BillingClient.newBuilder(this)
            .enablePendingPurchases()
            .setListener(this)
            .build()

        billingClient.startConnection(object : BillingClientStateListener {
            override fun onBillingSetupFinished(billingResult: BillingResult) {
                if (billingResult.responseCode == BillingClient.BillingResponseCode.OK) {
                    Log.d("MainActivity", "Billing ready")
                    // Optionally query purchases or SKUs right away
                } else {
                    Log.w("MainActivity", "Billing setup failed: ${billingResult.debugMessage}")
                }
            }

            override fun onBillingServiceDisconnected() {
                Log.w("MainActivity", "Billing service disconnected")
            }
        })
    }

    private fun startPurchaseFlow() {
        val params = SkuDetailsParams.newBuilder()
            .setSkusList(listOf(SKU_ID))
            .setType(BillingClient.SkuType.INAPP)
            .build()

        billingClient.querySkuDetailsAsync(params) { billingResult, skuDetailsList ->
            if (billingResult.responseCode == BillingClient.BillingResponseCode.OK && !skuDetailsList.isNullOrEmpty()) {
                val sku = skuDetailsList[0]
                val flowParams = BillingFlowParams.newBuilder().setSkuDetails(sku).build()
                billingClient.launchBillingFlow(this, flowParams)
            } else {
                Toast.makeText(this, "Product not available", Toast.LENGTH_SHORT).show()
            }
        }
    }

    override fun onPurchasesUpdated(billingResult: BillingResult, purchases: MutableList<Purchase>?) {
        if (billingResult.responseCode == BillingClient.BillingResponseCode.OK && purchases != null) {
            for (purchase in purchases) {
                handlePurchase(purchase)
            }
        } else if (billingResult.responseCode == BillingClient.BillingResponseCode.USER_CANCELED) {
            Toast.makeText(this, "Purchase canceled", Toast.LENGTH_SHORT).show()
        } else {
            Toast.makeText(this, "Purchase error: ${billingResult.debugMessage}", Toast.LENGTH_SHORT).show()
        }
    }

    private fun handlePurchase(purchase: Purchase) {
        // Acknowledge the purchase (recommended)
        if (purchase.purchaseState == Purchase.PurchaseState.PURCHASED) {
            if (!purchase.isAcknowledged) {
                val ackParams = AcknowledgePurchaseParams.newBuilder()
                    .setPurchaseToken(purchase.purchaseToken)
                    .build()
                billingClient.acknowledgePurchase(ackParams) { ackResult ->
                    if (ackResult.responseCode == BillingClient.BillingResponseCode.OK) {
                        // Send token to backend to grant credits
                        sendPurchaseTokenToServer(purchase.purchaseToken)
                    } else {
                        Log.w("MainActivity", "Ack failed: ${ackResult.debugMessage}")
                    }
                }
            } else {
                sendPurchaseTokenToServer(purchase.purchaseToken)
            }
        }
    }

    private fun sendPurchaseTokenToServer(purchaseToken: String) {
        val token = Storage.getToken(this) ?: run {
            Toast.makeText(this, "Login required to redeem purchase", Toast.LENGTH_SHORT).show()
            return
        }
        val bearer = "Bearer $token"
        val req = AddCreditsRequest(PACKAGE_NAME, SKU_ID, purchaseToken, 10) // grant 10 credits
        ApiClient.instance.addCredits(bearer, req).enqueue(object: Callback<Map<String, Any>> {
            override fun onResponse(call: Call<Map<String, Any>>, response: Response<Map<String, Any>>) {
                if (response.isSuccessful) {
                    Toast.makeText(this@MainActivity, "Credits added!", Toast.LENGTH_SHORT).show()
                } else {
                    Toast.makeText(this@MainActivity, "Server verification failed", Toast.LENGTH_SHORT).show()
                }
            }
            override fun onFailure(call: Call<Map<String, Any>>, t: Throwable) {
                Toast.makeText(this@MainActivity, "Network error: ${t.localizedMessage}", Toast.LENGTH_SHORT).show()
            }
        })
    }

    override fun onDestroy() {
        if (::billingClient.isInitialized) billingClient.endConnection()
        super.onDestroy()
    }
}

