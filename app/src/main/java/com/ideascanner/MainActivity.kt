package com.ideascanner

import android.os.Bundle
import android.widget.Button
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import com.google.android.gms.auth.api.signin.GoogleSignIn
import com.google.android.gms.auth.api.signin.GoogleSignInClient
import com.google.android.gms.auth.api.signin.GoogleSignInOptions
import com.google.android.gms.common.api.ApiException
import com.android.billingclient.api.*

class MainActivity : AppCompatActivity() {

    private lateinit var signInButton: Button
    private lateinit var buyButton: Button
    private lateinit var googleSignInClient: GoogleSignInClient
    private lateinit var billingClient: BillingClient

    private val RC_SIGN_IN = 100
    private val PRODUCT_ID = "idea_analysis" // must match Play Console

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        signInButton = findViewById(R.id.signInButton)
        buyButton = findViewById(R.id.buyButton)

        // ✅ Configure Google Sign-In
        val gso = GoogleSignInOptions.Builder(GoogleSignInOptions.DEFAULT_SIGN_IN)
            .requestEmail()
            .build()
        googleSignInClient = GoogleSignIn.getClient(this, gso)

        signInButton.setOnClickListener { signInWithGoogle() }

        // ✅ Setup Billing
        billingClient = BillingClient.newBuilder(this)
            .setListener { billingResult, purchases ->
                if (billingResult.responseCode == BillingClient.BillingResponseCode.OK && purchases != null) {
                    for (purchase in purchases) {
                        verifyPurchase(purchase)
                    }
                }
            }
            .enablePendingPurchases()
            .build()

        billingClient.startConnection(object : BillingClientStateListener {
            override fun onBillingSetupFinished(billingResult: BillingResult) {
                if (billingResult.responseCode == BillingClient.BillingResponseCode.OK) {
                    Toast.makeText(this@MainActivity, "Billing ready", Toast.LENGTH_SHORT).show()
                }
            }

            override fun onBillingServiceDisconnected() {
                Toast.makeText(this@MainActivity, "Billing service disconnected", Toast.LENGTH_SHORT).show()
            }
        })

        buyButton.setOnClickListener { launchPurchaseFlow() }
    }

    // 🔹 Google Sign-In Flow
    private fun signInWithGoogle() {
        val signInIntent = googleSignInClient.signInIntent
        startActivityForResult(signInIntent, RC_SIGN_IN)
    }

    override fun onActivityResult(requestCode: Int, resultCode: Int, data: android.content.Intent?) {
        super.onActivityResult(requestCode, resultCode, data)

        if (requestCode == RC_SIGN_IN) {
            val task = GoogleSignIn.getSignedInAccountFromIntent(data)
            try {
                val account = task.getResult(ApiException::class.java)
                Toast.makeText(this, "Signed in: ${account?.email}", Toast.LENGTH_SHORT).show()
            } catch (e: ApiException) {
                Toast.makeText(this, "Sign-in failed: ${e.statusCode}", Toast.LENGTH_SHORT).show()
            }
        }
    }

    // 🔹 Start Google Play Billing purchase
    private fun launchPurchaseFlow() {
        val skuList = listOf(PRODUCT_ID)
        val params = SkuDetailsParams.newBuilder()
            .setSkusList(skuList)
            .setType(BillingClient.SkuType.INAPP)
            .build()

        billingClient.querySkuDetailsAsync(params) { billingResult, skuDetailsList ->
            if (billingResult.responseCode == BillingClient.BillingResponseCode.OK && skuDetailsList != null) {
                for (skuDetails in skuDetailsList) {
                    val flowParams = BillingFlowParams.newBuilder()
                        .setSkuDetails(skuDetails)
                        .build()
                    billingClient.launchBillingFlow(this, flowParams)
                }
            }
        }
    }

    // 🔹 Verify purchase with your backend
    private fun verifyPurchase(purchase: Purchase) {
        // TODO: Send purchase.purchaseToken + purchase.products[0] to your Flask backend (/verify_purchase)
        Toast.makeText(this, "Purchase verified locally (send to backend)", Toast.LENGTH_SHORT).show()
    }
}


