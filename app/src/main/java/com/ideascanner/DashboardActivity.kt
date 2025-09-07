package com.ideascanner

import android.os.Bundle
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import com.android.billingclient.api.*
import com.ideascanner.databinding.ActivityDashboardBinding
import retrofit2.Call
import retrofit2.Callback
import retrofit2.Response

class DashboardActivity : AppCompatActivity(), PurchasesUpdatedListener {
    private lateinit var binding: ActivityDashboardBinding
    private lateinit var billingClient: BillingClient
    private val SKU_ID = "ideacredit_10" // your product id in Play Console
    private val PACKAGE_NAME = "com.ideascanner"

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityDashboardBinding.inflate(layoutInflater)
        setContentView(binding.root)

        billingClient = BillingClient.newBuilder(this)
            .enablePendingPurchases()
            .setListener(this)
            .build()

        billingClient.startConnection(object: BillingClientStateListener{
            override fun onBillingSetupFinished(billingResult: BillingResult) {
                if (billingResult.responseCode == BillingClient.BillingResponseCode.OK) {
                    // ready
                }
            }
            override fun onBillingServiceDisconnected() {}
        })

        binding.btnAnalyze.setOnClickListener {
            val idea = binding.etIdea.text.toString().trim()
            val location = binding.spinnerLocation.selectedItem as? String
            val token = Storage.getToken(this) ?: ""
            val bearer = "Bearer $token"
            ApiClient.instance.analyze(bearer, AnalyzeRequest(idea, location)).enqueue(object: Callback<AnalyzeResponse>{
                override fun onResponse(call: Call<AnalyzeResponse>, response: Response<AnalyzeResponse>) {
                    if (response.code() == 402) {
                        // show buy prompt
                        binding.tvResult.text = "Free limit exceeded. Buy credits."
                        binding.btnBuyCredits.apply {
                            isEnabled = true
                            setOnClickListener { startPurchaseFlow() }
                        }
                        return
                    }
                    val body = response.body()
                    if (body!=null && body.ok) {
                        binding.tvResult.text = "Score: ${body.score}\n\n${body.analysis}"
                    } else {
                        binding.tvResult.text = "Error analyzing idea."
                    }
                }
                override fun onFailure(call: Call<AnalyzeResponse>, t: Throwable) {
                    Toast.makeText(this@DashboardActivity, "Network error: ${t.localizedMessage}", Toast.LENGTH_SHORT).show()
                }
            })
        }

        binding.btnBuyCredits.setOnClickListener { startPurchaseFlow() }
    }

    private fun startPurchaseFlow() {
        val params = SkuDetailsParams.newBuilder()
            .setSkusList(listOf(SKU_ID))
            .setType(BillingClient.SkuType.INAPP)
            .build()
        billingClient.querySkuDetailsAsync(params) { billingResult, skuDetailsList ->
            if (billingResult.responseCode == BillingClient.BillingResponseCode.OK && !skuDetailsList.isNullOrEmpty()) {
                val flowParams = BillingFlowParams.newBuilder()
                    .setSkuDetails(skuDetailsList[0])
                    .build()
                billingClient.launchBillingFlow(this, flowParams)
            } else {
                Toast.makeText(this, "Unable to fetch product details", Toast.LENGTH_SHORT).show()
            }
        }
    }

    override fun onPurchasesUpdated(billingResult: BillingResult, purchases: MutableList<Purchase>?) {
        if (billingResult.responseCode == BillingClient.BillingResponseCode.OK && purchases != null) {
            for (purchase in purchases) {
                // Acknowledge and send token to backend to grant credits
                if (purchase.purchaseState == Purchase.PurchaseState.PURCHASED) {
                    if (!purchase.isAcknowledged) {
                        val ackParams = AcknowledgePurchaseParams.newBuilder()
                            .setPurchaseToken(purchase.purchaseToken)
                            .build()
                        billingClient.acknowledgePurchase(ackParams) { ackResult ->
                            if (ackResult.responseCode == BillingClient.BillingResponseCode.OK) {
                                sendPurchaseTokenToServer(purchase.purchaseToken)
                            }
                        }
                    } else {
                        sendPurchaseTokenToServer(purchase.purchaseToken)
                    }
                }
            }
        } else if (billingResult.responseCode == BillingClient.BillingResponseCode.USER_CANCELED) {
            Toast.makeText(this, "Purchase cancelled", Toast.LENGTH_SHORT).show()
        } else {
            Toast.makeText(this, "Error: ${billingResult.debugMessage}", Toast.LENGTH_SHORT).show()
        }
    }

    private fun sendPurchaseTokenToServer(purchaseToken: String) {
        val token = Storage.getToken(this) ?: return
        val bearer = "Bearer $token"
        val req = AddCreditsRequest(PACKAGE_NAME, SKU_ID, purchaseToken, 10) // grant 10 credits
        ApiClient.instance.addCredits(bearer, req).enqueue(object: Callback<Map<String, Any>>{
            override fun onResponse(call: Call<Map<String, Any>>, response: Response<Map<String, Any>>) {
                if (response.isSuccessful) {
                    Toast.makeText(this@DashboardActivity, "Credits added!", Toast.LENGTH_SHORT).show()
                } else {
                    Toast.makeText(this@DashboardActivity, "Server verification failed", Toast.LENGTH_SHORT).show()
                }
            }
            override fun onFailure(call: Call<Map<String, Any>>, t: Throwable) {
                Toast.makeText(this@DashboardActivity, "Network error: ${t.localizedMessage}", Toast.LENGTH_SHORT).show()
            }
        })
    }

    override fun onDestroy() {
        super.onDestroy()
        billingClient.endConnection()
    }
}
